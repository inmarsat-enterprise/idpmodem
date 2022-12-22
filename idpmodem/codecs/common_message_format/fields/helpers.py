import math


def optimal_bits(value_range: 'tuple[int, int]') -> int:
    """Returns the optimal number of bits for encoding a specified range.
    
    Args:
        value_range: A tuple with the minimum and maximum values.
    
    Returns:
        The number of bits to optimally encode the value.
    
    Raises:
        ValueError if the 

    """
    if (not isinstance(value_range, tuple) or
        len(value_range) != 2 or
        not all(isinstance(x, int) for x in value_range) or
        value_range[0] >= value_range[1]):
        #: non-compliant
        raise ValueError('value_range must be of form (min, max)')
    total_range = value_range[1] - value_range[0]
    total_range += 1 if value_range[0] == 0 else 0
    return max(1, math.ceil(math.log2(total_range)))


def encode_field_length(length) -> str:
    if length < 128:
        return f'0{length:07b}'
    return f'1{length:015b}'


def decode_field_length(binstr: str) -> 'tuple[int, int]':
    if binstr[0] == '0':
        bit_index = 8
    else:
        bit_index = 16
    length = int(binstr[1:bit_index], 2)
    return (length, bit_index)
