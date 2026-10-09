from app.plans import PLANS
def test_periods():
    assert [PLANS[k]["days"] for k in ("day","week","month","quarter")]==[1,7,30,90]
