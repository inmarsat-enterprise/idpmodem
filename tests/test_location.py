import json
from idpmodem import location

def test_basic():
    loc = location.Location()
    v = vars(loc)
    j = json.dumps(vars(loc), skipkeys=True)
    assert True
