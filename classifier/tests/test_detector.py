import fakeredis

from classifier.detector import StatefulDetector


def test_ddos_threshold():
    r = fakeredis.FakeRedis(decode_responses=True)
    det = StatefulDetector(r)
    ip = "192.168.1.99"
    triggered = False
    for _ in range(25):
        if det.record_and_check(ip, "request", window_sec=60, threshold=20):
            triggered = True
    assert triggered
