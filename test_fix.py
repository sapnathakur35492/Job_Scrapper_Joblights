"""
Test script to verify the fixed Jobright URL extractor.
Tests that Apply links resolve to company career pages, NOT Jobright pages.
"""
import logging
import sys
logging.basicConfig(level=logging.INFO, format='%(message)s')

from core.scrapers.jobright_extractor import extract_jobright_url

SEP = "=" * 65

# Test URLs from real jobs visible in the UI
test_urls = [
    'https://jobright.ai/jobs/info/69d9b0c2b67cec4f9b0a4042',   # SpaceX (from jobright.html)
    'https://jobright.ai/jobs/info/69f811ad81706a5bd216ca0a',   # General Dynamics (from screenshot)
]

passed = 0
failed = 0

for url in test_urls:
    print("\n" + SEP)
    print("Testing: " + url)
    print(SEP)
    result = extract_jobright_url(url)
    final = result.get('final_url') or ''
    status = result.get('status')
    
    # PASS = final URL does NOT contain jobright.ai
    is_company_url = final and 'jobright.ai' not in final
    verdict = "PASS" if is_company_url else "FAIL"
    
    print("Status:     " + str(status))
    print("Final URL:  " + str(final))
    print("Method:     " + str(result.get('method')))
    print("Title:      " + str(result.get('job_title')))
    print("Company:    " + str(result.get('company')))
    print("Confidence: " + str(result.get('confidence')))
    print("Time taken: " + str(result.get('time_taken')) + "s")
    print("Result:     " + verdict)
    
    if is_company_url:
        passed += 1
    else:
        failed += 1

print("\n" + SEP)
print("RESULTS: %d passed, %d failed out of %d tests" % (passed, failed, len(test_urls)))
print(SEP)
sys.exit(0 if failed == 0 else 1)
