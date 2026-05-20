"""
Sky API Client
Interaksi dengan Sky: Children of the Light API
Untuk account info, daily quests, stats, dll
"""

import requests
import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SkyAPIClient:
    """Client untuk Sky API"""
    
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self.base_url = "https://live.radiance.thatgamecompany.com"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Sky-Auto-CR-Bot/1.0'
        })
        
    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information
        
        Returns:
            Dict dengan account data atau None
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/account")
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Account info fetched for: {data.get('display_name', 'Unknown')}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return None
            
    def get_player_stats(self) -> Optional[Dict]:
        """
        Get player statistics
        
        Returns:
            Dict dengan player stats atau None
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/player/stats")
            response.raise_for_status()
            data = response.json()
            
            logger.info("Player stats fetched successfully")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching player stats: {e}")
            return None
            
    def get_daily_quests(self) -> Optional[List[Dict]]:
        """
        Get daily quests
        
        Returns:
            List of daily quests atau None
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/quests/daily")
            response.raise_for_status()
            data = response.json()
            
            quests = data.get('quests', [])
            logger.info(f"Found {len(quests)} daily quests")
            return quests
            
        except Exception as e:
            logger.error(f"Error fetching daily quests: {e}")
            return None
            
    def get_inventory(self) -> Optional[Dict]:
        """
        Get player inventory (candles, hearts, etc)
        
        Returns:
            Dict dengan inventory data atau None
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/player/inventory")
            response.raise_for_status()
            data = response.json()
            
            logger.info("Inventory fetched successfully")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
            return None
            
    def complete_quest(self, quest_id: str) -> bool:
        """
        Mark quest as completed
        
        Args:
            quest_id: Quest ID
            
        Returns:
            True if successful
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/quests/{quest_id}/complete"
            )
            response.raise_for_status()
            
            logger.info(f"Quest {quest_id} marked as complete")
            return True
            
        except Exception as e:
            logger.error(f"Error completing quest: {e}")
            return False
            
    def get_friends_list(self) -> Optional[List[Dict]]:
        """
        Get friends list
        
        Returns:
            List of friends atau None
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/friends")
            response.raise_for_status()
            data = response.json()
            
            friends = data.get('friends', [])
            logger.info(f"Found {len(friends)} friends")
            return friends
            
        except Exception as e:
            logger.error(f"Error fetching friends: {e}")
            return None


def format_account_info(account_data: Dict) -> str:
    """
    Format account info untuk display
    
    Args:
        account_data: Raw account data dari API
        
    Returns:
        Formatted string
    """
    if not account_data:
        return "❌ No account data available"
        
    lines = []
    lines.append("👤 <b>Account Information</b>\n")
    lines.append(f"📛 Name: {account_data.get('display_name', 'Unknown')}")
    lines.append(f"🆔 ID: {account_data.get('user_id', 'N/A')}")
    lines.append(f"⭐ Level: {account_data.get('level', 0)}")
    lines.append(f"🎭 Season Pass: {'✅' if account_data.get('has_season_pass') else '❌'}")
    
    # Inventory
    inventory = account_data.get('inventory', {})
    lines.append(f"\n💰 <b>Inventory:</b>")
    lines.append(f"🕯️ Candles: {inventory.get('candles', 0)}")
    lines.append(f"❤️ Hearts: {inventory.get('hearts', 0)}")
    lines.append(f"⚡ Ascended Candles: {inventory.get('ascended_candles', 0)}")
    lines.append(f"💎 Season Candles: {inventory.get('season_candles', 0)}")
    
    # Stats
    stats = account_data.get('stats', {})
    lines.append(f"\n📊 <b>Statistics:</b>")
    lines.append(f"⭐ Winged Light: {stats.get('winged_light', 0)}/200")
    lines.append(f"👥 Friends: {stats.get('friends_count', 0)}")
    lines.append(f"📅 Days Played: {stats.get('days_played', 0)}")
    lines.append(f"🏆 Spirits Unlocked: {stats.get('spirits_unlocked', 0)}")
    
    return "\n".join(lines)


def format_daily_quests(quests: List[Dict]) -> str:
    """
    Format daily quests untuk display
    
    Args:
        quests: List of daily quests
        
    Returns:
        Formatted string
    """
    if not quests:
        return "❌ No daily quests available"
        
    lines = []
    lines.append("📋 <b>Daily Quests</b>\n")
    
    for i, quest in enumerate(quests, 1):
        status = "✅" if quest.get('completed') else "⏳"
        lines.append(f"{status} <b>{i}. {quest.get('title', 'Unknown Quest')}</b>")
        lines.append(f"   📝 {quest.get('description', 'No description')}")
        lines.append(f"   🎁 Reward: {quest.get('reward', 'Unknown')}")
        
        if quest.get('progress'):
            current = quest['progress'].get('current', 0)
            total = quest['progress'].get('total', 1)
            percentage = (current / total) * 100 if total > 0 else 0
            lines.append(f"   📊 Progress: {current}/{total} ({percentage:.0f}%)")
            
        lines.append("")
        
    return "\n".join(lines)


# Mock data untuk testing tanpa API access
def get_mock_account_info() -> Dict:
    """Mock account info untuk testing"""
    return {
        'display_name': 'Sky Traveler',
        'user_id': '1234567890',
        'level': 15,
        'has_season_pass': True,
        'inventory': {
            'candles': 45,
            'hearts': 12,
            'ascended_candles': 8,
            'season_candles': 23
        },
        'stats': {
            'winged_light': 156,
            'friends_count': 42,
            'days_played': 127,
            'spirits_unlocked': 89
        }
    }


def get_mock_daily_quests() -> List[Dict]:
    """Mock daily quests untuk testing"""
    return [
        {
            'id': 'quest_1',
            'title': 'Relive a Memory',
            'description': 'Relive a spirit memory in any realm',
            'reward': '3 Seasonal Candles',
            'completed': False,
            'progress': {'current': 0, 'total': 1}
        },
        {
            'id': 'quest_2',
            'title': 'Light 20 Candles',
            'description': 'Light candles in Golden Wasteland',
            'reward': '2 Regular Candles',
            'completed': False,
            'progress': {'current': 8, 'total': 20}
        },
        {
            'id': 'quest_3',
            'title': 'Make Friends',
            'description': 'Wave to 5 different players',
            'reward': '1 Heart',
            'completed': True,
            'progress': {'current': 5, 'total': 5}
        },
        {
            'id': 'quest_4',
            'title': 'Meditate at Temple',
            'description': 'Meditate at Geyser in Daylight Prairie',
            'reward': '5 Regular Candles',
            'completed': False,
            'progress': {'current': 0, 'total': 1}
        }
    ]


if __name__ == "__main__":
    # Test mock data
    logging.basicConfig(level=logging.INFO)
    
    print("=== Mock Account Info ===")
    account = get_mock_account_info()
    print(format_account_info(account))
    
    print("\n=== Mock Daily Quests ===")
    quests = get_mock_daily_quests()
    print(format_daily_quests(quests))
