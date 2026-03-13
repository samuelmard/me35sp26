import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Twist

from irobot_create_msgs.action import Undock, NavigateToPosition, Dock
from irobot_create_msgs.srv import ResetPose
import testgrab
import time
import classifier

# INPUTS
bin1 = 'dustin'
bin2 = 'will'

class OriginNav(Node):
    def __init__(self):
        super().__init__('origin_nav_node')
        classifier.setup() # this may take a while to boot up
        # Separate action clients
        self.undock_client = ActionClient(self, Undock, 'undock')
        self.nav_client = ActionClient(self, NavigateToPosition, 'navigate_to_position')
        self.dock_client = ActionClient(self, Dock, 'dock')
        self.cli = self.create_client(ResetPose, '/reset_pose')
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        
    def detectChar(self):
        result = classifier.classify()
        character = ''
        if (result == 0): character = 'will'
        if (result == 1): character = 'dustin'
        print(f"I see {character}!")
        # pick up
        testgrab.grab()
        time.sleep(1)
        if (character == bin1):
            print("going to bin 1") # go to bin 1
            self.nav_to_pos(-0.86,0.7, math.pi/2)
        else:
            print("going to bin 2")
            self.nav_to_pos(-1.86,0.7, math.pi/2) # go to bin 2
        testgrab.release()
        time.sleep(2)   
        

    ## The important one that calls everything else
    def run(self):
        inp = input("Press enter to start")
        testgrab.setup()
        while (inp != 'q'):
            time.sleep(1)
            print("Reset Position")
            self.reset_pose()
            print("Undocking")
            self.undock()
            print("Navigate to First Character")
            # example nav commands
            self.nav_to_pos(-0.86,0,3*math.pi/2)
            self.nav_to_pos(-0.86,-0.6, 3*math.pi/2)
            self.move(0.1,0,0,0,0,0,1) # move forward 0.15 velocity for 2 seconds 
            self.detectChar()
            print("Navigate to Second Character")
            self.nav_to_pos(-1.86,-0.6, 3*math.pi/2)
            self.move(0.1,0,0,0,0,0,1)
            self.detectChar()
            # go home and dock
            self.nav_to_pos(-0.25,0,-math.pi)
            self.dock()
            inp = input("Press enter to restart")
        testgrab.cleanup()
    # shortened commands for ease of use
    def reset_pose(self):
        self.reset_pose_blocking()
    def undock(self):
        self.undock_blocking()
    def dock(self):
        self.dock_blocking()
    def nav_to_pos(self, x, y, a):
        self.nav_to_pos_blocking(x,y,a)
    # Twist so it doesn't knock the guy off before it gets there
    def send_twist(self, lx, ly, lz, ax, ay, az):
        msg = Twist()
        msg.linear.x = float(lx)
        msg.linear.y = float(ly)
        msg.linear.z = float(lz)
        msg.angular.x = float(ax)
        msg.angular.y = float(ay)
        msg.angular.z = float(az)
        self.cmd_vel_pub.publish(msg)
    def stop_twist(self):
        self.send_twist(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    def send_twist_blocking(self, lx, ly, lz, ax, ay, az, duration, rate_hz=20.0):
        msg = Twist()
        msg.linear.x = float(lx)
        msg.linear.y = float(ly)
        msg.linear.z = float(lz)
        msg.angular.x = float(ax)
        msg.angular.y = float(ay)
        msg.angular.z = float(az)

        end_time = self.get_clock().now().nanoseconds / 1e9 + float(duration)
        period = 1.0 / float(rate_hz)

        while rclpy.ok() and (self.get_clock().now().nanoseconds / 1e9) < end_time:
            self.cmd_vel_pub.publish(msg)
            time.sleep(period)

        self.stop_twist()
    def twist(self, lx, ly, lz, ax, ay, az):
        self.send_twist(lx, ly, lz, ax, ay, az)
    def move(self, lx, ly, lz, ax, ay, az, duration, rate_hz=20.0):
        self.send_twist_blocking(lx, ly, lz, ax, ay, az, duration, rate_hz)
    # Reset_Pose
    def send_request(self):
        req = ResetPose.Request()
        future = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        # self.send_next_goal()
        return future.result()
    
    # UNDOCK ACTION
    def undock_send_goal(self):
        self.get_logger().info('Waiting for undock action server...')
        self.undock_client.wait_for_server()

        goal_msg = Undock.Goal()

        self.get_logger().info('Sending undock goal...')
        self.undock_send_future = self.undock_client.send_goal_async(
            goal_msg,
            feedback_callback=self.undock_feedback_callback
        )
        self.undock_send_future.add_done_callback(self.undock_goal_response_callback)

    def undock_goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().info('Undock goal rejected')
            rclpy.shutdown()
            return

        self.get_logger().info('Undock goal accepted')
        self.undock_result_future = goal_handle.get_result_async()
        self.undock_result_future.add_done_callback(self.undock_get_result_callback)

    def undock_get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f'Final Docking Status: {result.is_docked}')

        # After undocking, begin navigation
        self.get_logger().info('Starting navigation sequence...')
        #response = self.send_request()
        # self.get_logger().info(f'Response: {response}')

    def undock_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f'Robot sees dock: {feedback.sees_dock}')


    # NAVIGATION ACTION
    def send_nav_goal(self, x, y, theta):

        goal_msg = NavigateToPosition.Goal()
        goal_msg.achieve_goal_heading = True
        goal_msg.goal_pose.header.frame_id = 'odom'

        goal_msg.goal_pose.pose.position.x = float(x)
        goal_msg.goal_pose.pose.position.y = float(y)
        goal_msg.goal_pose.pose.position.z = 0.0

        # Planar yaw -> quaternion
        goal_msg.goal_pose.pose.orientation.x = 0.0
        goal_msg.goal_pose.pose.orientation.y = 0.0
        goal_msg.goal_pose.pose.orientation.z = math.sin(theta / 2.0)
        goal_msg.goal_pose.pose.orientation.w = math.cos(theta / 2.0)

        self.get_logger().info(
            f'Sending goal : x={x}, y={y}, theta={theta:.3f} rad'
        )

        self.nav_client.wait_for_server()
        self.nav_send_future = self.nav_client.send_goal_async(goal_msg)
        self.nav_send_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().info(f'Navigation goal rejected')
            rclpy.shutdown()
            return

        self.get_logger().info(f'Navigation goal accepted')
        self.nav_result_future = goal_handle.get_result_async()
        self.nav_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f'Navigation goal finished')
        

    # DOCKING
    def dock_send_goal(self):
        self.get_logger().info('Waiting for undock action server...')
        self.dock_client.wait_for_server()

        goal_msg = Dock.Goal()

        self.get_logger().info('Sending undock goal...')
        self.dock_send_future = self.dock_client.send_goal_async(
            goal_msg,
            feedback_callback=self.dock_feedback_callback
        )
        self.dock_send_future.add_done_callback(self.dock_goal_response_callback)

    def dock_goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().info('Dock goal rejected')
            rclpy.shutdown()
            return

        self.get_logger().info('Dock goal accepted')
        self.dock_result_future = goal_handle.get_result_async()
        self.dock_result_future.add_done_callback(self.dock_get_result_callback)

    def dock_get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f'Final Docking Status: {result.is_docked}')


    def dock_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f'Robot sees dock: {feedback.sees_dock}')
    
    # Chat Wrote Blocking Functions that are equivalent except they wait 
    # until the action is done to start the next one by using
    # spin_until_future_complete command
    # this makes it much easier to code the run function
    def reset_pose_blocking(self):
        req = ResetPose.Request()
        future = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        response = future.result()
        if response is None:
            raise RuntimeError('reset_pose service call failed')
        return response

    def undock_blocking(self):
        self.get_logger().info('Waiting for undock action server...')
        self.undock_client.wait_for_server()

        goal_msg = Undock.Goal()
        self.get_logger().info('Sending undock goal...')

        send_future = self.undock_client.send_goal_async(
            goal_msg,
            feedback_callback=self.undock_feedback_callback
        )
        rclpy.spin_until_future_complete(self, send_future)

        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            raise RuntimeError('undock goal rejected')

        self.get_logger().info('Undock goal accepted')

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        if result is None:
            raise RuntimeError('undock result failed')

        self.get_logger().info(f'Final Docking Status: {result.result.is_docked}')
        return result.result

    def nav_to_pos_blocking(self, x, y, theta):
        goal_msg = NavigateToPosition.Goal()
        goal_msg.achieve_goal_heading = True
        goal_msg.goal_pose.header.frame_id = 'odom'
        goal_msg.goal_pose.pose.position.x = float(x)
        goal_msg.goal_pose.pose.position.y = float(y)
        goal_msg.goal_pose.pose.position.z = 0.0
        goal_msg.goal_pose.pose.orientation.x = 0.0
        goal_msg.goal_pose.pose.orientation.y = 0.0
        goal_msg.goal_pose.pose.orientation.z = math.sin(theta / 2.0)
        goal_msg.goal_pose.pose.orientation.w = math.cos(theta / 2.0)

        self.get_logger().info(f'Sending goal: x={x}, y={y}, theta={theta:.3f} rad')

        self.nav_client.wait_for_server()
        send_future = self.nav_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_future)

        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            raise RuntimeError('navigation goal rejected')

        self.get_logger().info('Navigation goal accepted')

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        if result is None:
            raise RuntimeError('navigation result failed')

        self.get_logger().info('Navigation goal finished')
        return result.result

    def dock_blocking(self):
        self.get_logger().info('Waiting for dock action server...')
        self.dock_client.wait_for_server()

        goal_msg = Dock.Goal()
        self.get_logger().info('Sending dock goal...')

        send_future = self.dock_client.send_goal_async(
            goal_msg,
            feedback_callback=self.dock_feedback_callback
        )
        rclpy.spin_until_future_complete(self, send_future)

        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            raise RuntimeError('dock goal rejected')

        self.get_logger().info('Dock goal accepted')

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        if result is None:
            raise RuntimeError('dock result failed')

        self.get_logger().info(f'Final Docking Status: {result.result.is_docked}')
        return result.result

def main(args=None):
    rclpy.init(args=args)
    node = OriginNav()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()