import time

def test_benchmark_dns_lookup():
    hostname = "asgsearch.local"
    start_time = time.time()
    # DNS lookup logic would go here
    end_time = time.time()
    print(f"DNS Lookup Time: {end_time - start_time:.4f}s")
