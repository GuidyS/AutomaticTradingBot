import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz

class NewsFilter:
    def __init__(self, logger):
        self.logger = logger
        self.news_events = []
        self.last_fetch = None
        self.update_interval = timedelta(hours=6)

    def fetch_news(self):
        """Fetch news from Forex Factory XML feed"""
        if self.last_fetch and (datetime.now() - self.last_fetch) < timedelta(hours=1):
             return

        try:
            url = "https://www.forexfactory.com/ff_calendar_thisweek.xml"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                events = []
                for event in tree.findall('event'):
                    symbol = event.find('country').text
                    impact = event.find('impact').text
                    if symbol == "USD" and impact == "High":
                        date_str = event.find('date').text
                        time_str = event.find('time').text
                        try:
                            dt_str = f"{date_str} {time_str}"
                            dt = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                            est = pytz.timezone('US/Eastern')
                            dt = est.localize(dt).astimezone(pytz.utc)
                            events.append(dt)
                        except: continue
                self.news_events = events
                self.last_fetch = datetime.now()
                self.logger.info(f"News Filter: Updated successfully ({len(events)} events found).")
            else:
                raise Exception(f"HTTP {response.status_code}")

        except Exception as e:
            # Silent fallback: Don't crash, just log once and wait an hour
            self.last_fetch = datetime.now()
            self.logger.warning(f"News Filter: Unreachable (DNS/Network). Trading will continue without news filter for 1 hour.")

    def is_safe_to_trade(self, avoidance_mins=30):
        """Check if current time is outside the news danger zone"""
        self.fetch_news()
        
        if not self.news_events:
            return True, 0 # Safe to trade if no news data

        now_utc = datetime.now(pytz.utc)
        for news_time in self.news_events:
            start_danger = news_time - timedelta(minutes=avoidance_mins)
            end_danger = news_time + timedelta(minutes=avoidance_mins)
            if start_danger <= now_utc <= end_danger:
                mins_left = (news_time - now_utc).total_seconds() / 60
                return False, mins_left

        return True, 0
