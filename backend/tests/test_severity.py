from app.services.severity import calculate_severity
def test_severity_ranges():
    assert calculate_severity(1,100000,0.4,"transverse_crack").label == "Low"
    assert calculate_severity(50000,100000,0.9,"pothole").label == "High"
