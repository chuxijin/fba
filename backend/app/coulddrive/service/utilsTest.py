import unittest
from datetime import datetime
from typing import Union


def format_time(time_input: Union[int, float, str]) -> str:
    """
    将时间输入转换为标准格式的日期时间字符串
    
    支持毫秒级时间戳、Unix时间戳和ISO 8601格式字符串
    
    参数:
        time_input (Union[int, float, str]): 时间输入，可以是：
            - 毫秒级时间戳(>9999999999)
            - Unix时间戳(秒)
            - ISO 8601格式字符串
    
    返回:
        str: 格式化的日期时间字符串"YYYY-MM-DD HH:MM:SS"，无效输入返回空字符串
    """
    try:
        if isinstance(time_input, (int, float)):
            # 处理时间戳（秒级或毫秒级）
            if time_input > 9999999999:  # 毫秒级时间戳
                time_input = time_input / 1000
            return datetime.fromtimestamp(time_input).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(time_input, str):
            # 处理日期时间字符串
            # 尝试解析ISO 8601格式
            if "T" in time_input:
                try:
                    dt = datetime.strptime(time_input, "%Y-%m-%dT%H:%M:%S")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            else:
                try:
                    dt = datetime.strptime(time_input, "%Y-%m-%d %H:%M:%S")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            return ""
        return ""
    except (ValueError, TypeError, OverflowError, OSError):
        return ""


class UtilsTest(unittest.TestCase):
    def test_format_time_millisecond_timestamp_conversion(self):
        """Test conversion of a millisecond timestamp to formatted datetime string"""
        # Input
        time_input = 1617456000000
        
        # Expected outcome
        expected_output = "2021-04-03 18:00:00"
        
        # Call the function
        actual_output = format_time(time_input)
        
        # Assert the result
        self.assertEqual(actual_output, expected_output)

    def test_unix_timestamp_conversion_to_formatted_datetime(self):
        """
        Test conversion of a Unix timestamp (seconds) to formatted datetime string
        """
        # Input: Unix timestamp in seconds
        time_input = 1617456000
        
        # Expected outcome
        expected_output = "2021-04-03 18:00:00"
        
        # Call the function
        result = format_time(time_input)
        
        # Assert the result matches expected output
        self.assertEqual(result, expected_output)

    def test_format_time_iso8601_with_t_separator(self):
        """
        Test conversion of ISO 8601 format string with T separator
        """
        # Input
        time_input = "2021-04-03T18:00:00"
        
        # Expected outcome
        expected_output = "2021-04-03 18:00:00"
        
        # Call the function
        actual_output = format_time(time_input)
        
        # Assert the result
        self.assertEqual(actual_output, expected_output)

    def test_invalid_date_string_format(self):
        """
        Test handling of completely invalid date string
        Input: "not a date"
        Expected Outcome: "" (empty string)
        """
        # Test input
        test_input = "not a date"
        
        # Call the function
        result = format_time(test_input)
        
        # Assert the result is an empty string
        self.assertEqual(result, "")


if __name__ == '__main__':
    unittest.main()