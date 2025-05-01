import numpy as np
from typing import List, Tuple, Dict
import pandas as pd

class SupportResistanceAnalyzer:
    def __init__(self, price_data: pd.DataFrame, window_size: int = 20):
        """
        Initialize the analyzer with price data.
        
        Args:
            price_data (pd.DataFrame): DataFrame containing OHLCV data
            window_size (int): Window size for identifying consolidation zones
        """
        self.price_data = price_data
        self.window_size = window_size
        
    def find_consolidation_zones(self) -> List[Dict]:
        """
        Find yellow consolidation zones where price spent significant time.
        Returns list of zones with their price ranges and durations.
        """
        zones = []
        high = self.price_data['high']
        low = self.price_data['low']
        
        # Calculate price range for each window
        for i in range(len(self.price_data) - self.window_size):
            window_high = high.iloc[i:i+self.window_size].max()
            window_low = low.iloc[i:i+self.window_size].min()
            range_pct = (window_high - window_low) / window_low * 100
            
            # If price range is small, it's a consolidation zone
            if range_pct < 2:  # 2% range threshold
                zones.append({
                    'type': 'consolidation',
                    'start_price': window_low,
                    'end_price': window_high,
                    'start_time': self.price_data.index[i],
                    'end_time': self.price_data.index[i+self.window_size],
                    'color': 'yellow'
                })
        
        return zones
    
    def find_temporary_resistance(self) -> List[Dict]:
        """
        Find purple temporary resistance levels above consolidation zones.
        These are typically areas with low volume or price gaps.
        """
        resistance_levels = []
        close = self.price_data['close']
        volume = self.price_data['volume']
        
        # Find local highs with low volume
        for i in range(1, len(self.price_data)-1):
            if (close.iloc[i] > close.iloc[i-1] and 
                close.iloc[i] > close.iloc[i+1] and 
                volume.iloc[i] < volume.iloc[i-1:i+2].mean() * 0.7):
                resistance_levels.append({
                    'type': 'temporary_resistance',
                    'price': close.iloc[i],
                    'time': self.price_data.index[i],
                    'color': 'purple'
                })
        
        return resistance_levels
    
    def find_psychological_peaks(self) -> List[Dict]:
        """
        Find green psychological major peaks that have been tested multiple times.
        """
        peaks = []
        high = self.price_data['high']
        
        # Find significant peaks that have been tested multiple times
        for i in range(2, len(self.price_data)-2):
            if (high.iloc[i] > high.iloc[i-1] and 
                high.iloc[i] > high.iloc[i+1] and
                high.iloc[i] > high.iloc[i-2] and
                high.iloc[i] > high.iloc[i+2]):
                # Check if this level has been tested before
                test_count = sum(abs(high - high.iloc[i]) < high.iloc[i] * 0.01)
                if test_count > 3:  # Level tested at least 3 times
                    peaks.append({
                        'type': 'psychological_peak',
                        'price': high.iloc[i],
                        'time': self.price_data.index[i],
                        'color': 'green'
                    })
        
        return peaks
    
    def find_bottom_support(self) -> List[Dict]:
        """
        Find red bottom support levels that have shown strong buying pressure.
        """
        support_levels = []
        low = self.price_data['low']
        volume = self.price_data['volume']
        
        # Find significant lows with high volume
        for i in range(2, len(self.price_data)-2):
            if (low.iloc[i] < low.iloc[i-1] and 
                low.iloc[i] < low.iloc[i+1] and
                volume.iloc[i] > volume.iloc[i-2:i+3].mean() * 1.5):
                support_levels.append({
                    'type': 'bottom_support',
                    'price': low.iloc[i],
                    'time': self.price_data.index[i],
                    'color': 'red'
                })
        
        return support_levels
    
    def analyze(self) -> Dict:
        """
        Perform complete support and resistance analysis.
        Returns a dictionary containing all identified levels and zones.
        """
        return {
            'consolidation_zones': self.find_consolidation_zones(),
            'temporary_resistance': self.find_temporary_resistance(),
            'psychological_peaks': self.find_psychological_peaks(),
            'bottom_support': self.find_bottom_support()
        }
