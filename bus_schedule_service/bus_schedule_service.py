import os
import json
import time
import schedule
from datetime import datetime, timedelta
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
import paho.mqtt.publish as publish
import sys

# Constants and Configuration
TIMETABLE_TYPES = {
    'darbo diena': 'workday',
    'šeštadienis': 'saturday',
    'sekmadienis': 'sunday'
}

class TimetableScraper:
    def __init__(self):
        self.driver = self._initialize_driver()

    def _initialize_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        return webdriver.Chrome(options=options)

    def extract_params_from_url(self, url):
        parts = urlparse(url)
        path = parts.fragment.split('/')
        bus_number = path[1]
        direction = path[2]
        stop_id = path[3]
        return bus_number, stop_id, direction

    def fetch_timetable(self, url, type):        
        try:
            self.driver.get(url)
            time.sleep(5)  # Allow time for the page to load
            
            timetable_div = self.driver.find_element(By.ID, 'divScheduleContentInner')
            rows = timetable_div.find_elements(By.TAG_NAME, 'tr')
            current_type = ''
            timetable = []            
        except:
            return

        for row in rows:
            try:
                if row.text in TIMETABLE_TYPES:
                    current_type = row.text
                if current_type == type:
                    hour = row.find_element(By.TAG_NAME, 'th').text.strip()
                    minute_elements = row.find_elements(By.TAG_NAME, 'td')
                    for minute_element in minute_elements:
                        minute_text = minute_element.text.strip()
                        if minute_text:
                            minutes = [minute_text[i:i + 2] for i in range(0, len(minute_text), 2)]
                            for minute in minutes:
                                timetable.append(f"{hour}:{minute.zfill(2)}")
            except:
                continue

        return timetable

    def close(self):
        self.driver.quit()

class TimetableManager:
    def __init__(self):        
        data_folder = os.path.join(os.path.dirname(__file__), 'data')
        self.data_folder = data_folder
        os.makedirs(self.data_folder, exist_ok=True)

    def save_timetable(self, data, bus_number, stop_id, direction, type):
        filename = self._get_filename(bus_number, stop_id, direction, type)
        filepath = os.path.join(self.data_folder, filename)

        with open(filepath, 'w') as f:
            json.dump(data, f)
        print(f"Timetable saved to {filepath}")

    def load_timetable(self, bus_number, stop_id, direction, day_type):
        filename = self._get_filename(bus_number, stop_id, direction, day_type)
        filepath = os.path.join(self.data_folder, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None    

    def load_timetable_filename(self, filename):
        """Load the timetable from the correct JSON file based on file name."""
        data_folder = os.path.join(os.path.dirname(__file__), 'data')
        filepath = os.path.join(data_folder, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None

    def _get_filename(self, bus_number, stop_id, direction, day_type):
        # Use day_type directly here
        return f'timetable_{bus_number}_{stop_id}_{direction}_{day_type}.json'

class MQTTPublisher:
    def __init__(self, mqtt_host, mqtt_port, mqtt_user, mqtt_password, mqtt_topic):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.mqtt_topic = mqtt_topic
        self.homeassistant_topic = 'homeassistant'
        self.node_id = mqtt_topic

    def publish_data(self, bus_number, stop_id, direction, entity, payload, is_long_text = False):
        # If the payload is too long for the state, put it in the attributes instead
        if is_long_text:
            short_payload = "Long text stored in attributes"
            attributes = {
                "long_text": payload  # Store the long text as an attribute
            }
        else:
            short_payload = payload  # This is the regular state payload
            attributes = {}

        # Set up the MQTT discovery topics for the sensor
        topic_sensor = f"{self.homeassistant_topic}/sensor/{self.mqtt_topic}/{bus_number}_{stop_id}_{direction}_{entity}/config"
        topic_state = f"{self.homeassistant_topic}/sensor/{self.mqtt_topic}/{bus_number}_{stop_id}_{direction}_{entity}/state"
        topic_attributes = f"{self.homeassistant_topic}/sensor/{self.mqtt_topic}/{bus_number}_{stop_id}_{direction}_{entity}/attributes"

        # Configure the sensor for discovery
        config_template = {
            "name": f"{bus_number} {stop_id} {direction} {entity.replace('_', ' ').title()}",
            "unique_id": f"{self.node_id}_{entity}_{bus_number}_{stop_id}_{direction}",
            "state_topic": topic_state,
            "json_attributes_topic": topic_attributes,  # Topic for attributes
            "device": {
                "identifiers": [self.node_id],
                "name": "Autobusų tvarkaraštis",
                "model": "Timetable Publisher",
                "manufacturer": "stops.lt"
            },
            "enabled_by_default": True
        }

        # Create a list of MQTT messages
        messages = [
            {
                'topic': topic_sensor,
                'payload': json.dumps(config_template),
                'qos': 1,
                'retain': True
            },
            {
                'topic': topic_state,
                'payload': short_payload,  # State payload (shortened or original)
                'qos': 1,
                'retain': True
            }
        ]

        # Publish the attributes if there are any
        if attributes:
            messages.append({
                'topic': topic_attributes,
                'payload': json.dumps(attributes),
                'qos': 1,
                'retain': True
            })

        # Publish the messages to MQTT
        for msg in messages:
            publish.single(msg['topic'], msg['payload'], hostname=self.mqtt_host, port=self.mqtt_port,
                           auth={'username': self.mqtt_user, 'password': self.mqtt_password}, qos=msg['qos'], retain=msg['retain'])

class BusScheduleService:
    def __init__(self, scraper, manager, publisher):
        self.scraper = scraper
        self.manager = manager
        self.publisher = publisher

    # Scraping only
    def scrape(self, urls):
        print("Updating timetables from stops.lt server...")
        for url in urls:
            bus_number, stop_id, direction = self.scraper.extract_params_from_url(url)
            for type in TIMETABLE_TYPES:
                timetable = self.scraper.fetch_timetable(url, type)
                
                self.manager.save_timetable(timetable, bus_number, stop_id, direction, TIMETABLE_TYPES[type])

    # Publishing only
    def publish_timetables(self):        
        print("Publishing timetables...")
        # Publish all saved timetables
        for type in TIMETABLE_TYPES.values():
            for filename in os.listdir(self.manager.data_folder):
                if filename.endswith('.json'):
                    bus_number, stop_id, direction, _ = filename.replace('timetable_', '').replace('.json', '').split('_')

                timetable = self.manager.load_timetable(bus_number, stop_id, direction, type)

                if timetable == None:
                    continue  # Skip if no timetable for today

                payload = ",".join(timetable)
                
                self.publisher.publish_data(bus_number, stop_id, direction, f"{type}_timetable", payload, True)

                timetable = None

    def publish_departures(self):
        print("Publishing departures...")
        data_folder = os.path.join(os.path.dirname(__file__), 'data')
        timetable_files = [f for f in os.listdir(data_folder) if f.startswith('timetable_')]

        for filename in timetable_files:
            parts = filename.replace('timetable_', '').replace('.json', '').split('_')
            bus_number, stop_id, direction, day_type = parts[:4]

            # Determine today's timetable file based on the current weekday
            today_day_type = self._get_current_day_type()

            if (day_type == today_day_type):
                timetable = self.manager.load_timetable_filename(filename)
            else:
                continue  # Skip if no timetable for today

            current_departure, next_departure = self._get_next_departures(timetable, today_day_type, bus_number, stop_id, direction)

            # Check if current time is later than the last departure of the day
            last_departure_time = datetime.strptime(timetable[-1], "%H:%M").time()
            now_time = datetime.now().time()

            if now_time > last_departure_time:
                # It's after the last departure, load the next day's timetable
                next_day_type = self._get_next_day_type(today_day_type)
                timetable = self.manager.load_timetable(bus_number, stop_id, direction, next_day_type)

                if timetable:
                    current_departure = timetable[0]
                    next_departure = timetable[1]

            # Publish the data for the selected timetable (either today or the next day)
            self.publisher.publish_data(bus_number, stop_id, direction, "current_departure", current_departure)
            self.publisher.publish_data(bus_number, stop_id, direction, "current_departure_remaining", self._minutes_remaining(current_departure))
            self.publisher.publish_data(bus_number, stop_id, direction, "next_departure", next_departure)
            self.publisher.publish_data(bus_number, stop_id, direction, "next_departure_remaining", self._minutes_remaining(next_departure))

            timetable = None

    def _get_current_day_type(self):
        """Determine if today is a workday, saturday, or sunday."""
        weekday = datetime.now().weekday()  # 0 = Monday, 6 = Sunday
        
        if weekday < 5:  # Monday to Friday are workdays
            return 'workday'
        elif weekday == 5:  # Saturday
            return 'saturday'
        else:  # Sunday
            return 'sunday'           

    def _get_next_day_type(self, current_day_type):
        """Determine the next day type based on the current day."""
        day_types = ['workday', 'saturday', 'sunday']
        current_idx = day_types.index(current_day_type)
        next_idx = (current_idx + 1) % len(day_types)  # Loop back to the beginning
        return day_types[next_idx]

    def _minutes_until_departure(self, departure_time_str):
        """Calculate the minutes remaining until the next departure."""
        now = datetime.now()
        departure_time = datetime.strptime(departure_time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)

        # If the departure time has already passed, treat it as tomorrow's departure
        if departure_time < now:
            departure_time += timedelta(days=1)

        return int((departure_time - now).total_seconds() / 60)

    def _get_next_departures(self, timetable, today_day_type, bus_number, stop_id, direction):
        now = datetime.now().time()
        timetable_times = [datetime.strptime(time, "%H:%M").time() for time in timetable]

        current_departure = next_departure = None

        for time in timetable_times:
            if time >= now and current_departure is None:
                current_departure = time
            elif time > now:
                next_departure = time
                break

        if current_departure is None:
            current_departure = timetable_times[0]
        
        #If there is no next departure, pick other days timetables first time
        if next_departure is None:
            next_day_type = self._get_next_day_type(today_day_type)
            next_day_timetable = self.manager.load_timetable(bus_number, stop_id, direction, next_day_type)
            next_day_timetable_times = [datetime.strptime(time, "%H:%M").time() for time in next_day_timetable]
            next_departure = next_day_timetable_times[0] if len(next_day_timetable_times) > 1 else current_departure

        return current_departure.strftime("%H:%M"), next_departure.strftime("%H:%M")
    
    def _minutes_remaining(self, time_str):
        # Parse the input time string (e.g., "12:30") into a time object
        target_time = datetime.strptime(time_str, "%H:%M").time()
        
        # Get the current time
        now = datetime.now()
        
        # Create a datetime object for today with the target time
        target_datetime = datetime.combine(now.date(), target_time)
        
        # If the target time has already passed today, set the target time to tomorrow
        if target_datetime < now:
            target_datetime += timedelta(days=1)
        
        # Calculate the difference in time (in minutes)
        time_diff = target_datetime - now
        minutes_diff = time_diff.total_seconds() / 60  # Convert seconds to minutes
        
        return int(minutes_diff)

class ScheduleRunner:
    def __init__(self, bus_service):
        self.bus_service = bus_service

    def start_schedule(self, urls):
        # Execute the following on startup:
        print("Initial scrape and publish...")
        self.bus_service.scrape(urls)
        self.bus_service.publish_departures()  # Publish departures immediately after scraping
        self.bus_service.publish_timetables()             # Publish timetables immediately after scraping

        # Now, schedule tasks to run periodically:
        # Schedule the scraping every 12 hours
        schedule.every(12).hours.do(lambda: self.bus_service.scrape(urls))
        
        # Schedule publishing timetables every 6 hours
        schedule.every(6).hours.do(self.bus_service.publish_timetables)
        
        # Schedule publishing departures every 10 seconds
        schedule.every(10).seconds.do(self.bus_service.publish_departures)
        
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    print("Starting the application...")
    mqtt_host = os.getenv('MQTT_HOST')
    mqtt_port = os.getenv('MQTT_PORT')
    mqtt_user = os.getenv('MQTT_USER')
    mqtt_password = os.getenv('MQTT_PASSWORD')
    urls_env = os.getenv('URLS')

    # Check if essential configurations are provided
    if not mqtt_host or not mqtt_port or not mqtt_user or not mqtt_password or not urls_env:
        print("Error: Missing required configuration. Ensure mqtt_host, mqtt_port, mqtt_user, mqtt_password, and urls are set.")
        sys.exit(1)

    # Parse URLs (comma-separated or list format)
    urls = urls_env.split(',') if urls_env else []
    if not urls:
        print("Error: No URLs provided for scraping. Please set the 'urls' configuration.")
        sys.exit(1)

    # Convert mqtt_port to integer
    try:
        mqtt_port = int(mqtt_port)
    except ValueError:
        print("Error: mqtt_port must be an integer.")
        sys.exit(1)

    urls = urls_env.split(',') 
    
    # Initialize components
    scraper = TimetableScraper()
    manager = TimetableManager()
    publisher = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_password, 'stops_lt')
    bus_service = BusScheduleService(scraper, manager, publisher)

    # Start the schedule runner
    runner = ScheduleRunner(bus_service)
    runner.start_schedule(urls)

    # Close the scraper when done
    scraper.close()
