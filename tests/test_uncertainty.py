from rift.uncertainty import normalized_entropy

def test_entropy_uniform_is_positive():
    assert normalized_entropy([1,1,1]) > 0

def test_entropy_empty_is_zero():
    assert normalized_entropy([]) == 0
