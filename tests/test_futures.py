from rift.futures import branch_futures
from rift.scenarios import emergency_building

def test_future_tree_has_multiple_depths():
    tree = branch_futures(emergency_building(), depth=2)
    assert tree.max_depth == 2
    assert len(tree.nodes) == 2**3 + 2**6
    assert any(node.parent_id for node in tree.nodes)
