import requests
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

# Airtable Config
URL = 'https://api.airtable.com/v0/appaJO2dIW2rN53qb/Table 2'
# HEADERS = {'Authorization':'Bearer (PERSONAL ACCESS TOKEN)'}

class AirtableJsonController(Node):
    def __init__(self):
        super().__init__('airtable_json_controller')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
       
        # This maps your Airtable button text to robot math
        # Format: (Linear X speed, Angular Z speed)
        self.move_map = {
            "Forward":  (0.2, 0.0),
            "Backward": (-0.2, 0.0),
            "Left":     (0.0, 0.8),
            "Right":    (0.0, -0.8),
            "Stop":     (0.0, 0.0)
        }

        # Timer checks Airtable every 0.2 seconds
        self.timer = self.create_timer(0.1, self.fetch_and_move)
        self.get_logger().info('Airtable Simple Controller Active')

    def fetch_and_move(self):
        try:
            # Fetch data from Airtable
            response = requests.get(url=URL, headers=HEADERS, timeout=0.15)
            data = response.json()
           
            # Default to stop if something goes wrong
            lin_x, ang_z = 0.0, 0.0

            # Look for the 'Yummy yummy yummy' record in the list
            for record in data.get('records', []):
                fields = record.get('fields', {})
                if fields.get('Name') == 'Yummy yummy yummy':
                    status = fields.get('Status')
                   
                    # Apply the speeds from our map
                    if status in self.move_map:
                        lin_x, ang_z = self.move_map[status]
           
            # Send the command to the Create 3
            msg = Twist()
            msg.linear.x = float(lin_x)
            msg.angular.z = float(ang_z)
            self.publisher_.publish(msg)

        except Exception as e:
            # Emergency stop if internet fails
            self.publisher_.publish(Twist())
            self.get_logger().error(f'API Error: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = AirtableJsonController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Stop robot on Ctrl+C
        node.publisher_.publish(Twist())
        rclpy.shutdown()

if __name__ == '__main__':
    main()