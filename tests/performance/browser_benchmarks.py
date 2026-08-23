import time

def test_benchmark_html_parsing():
    html_content = "<html><body>" + ("<p>Test</p>" * 1000) + "</body></html>"
    start_time = time.time()
    # Parsing logic would go here
    end_time = time.time()
    print(f"HTML Parsing Time: {end_time - start_time:.4f}s")
