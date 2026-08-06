const UNCRUFT_TEST_CASES = [
  {
    "name": "UTM parameters are removed",
    "input": "https://example.com/a?id=42&utm_source=chatgpt.com&utm_medium=referral",
    "expected": "https://example.com/a?id=42",
    "mode": "navigation"
  },
  {
    "name": "Functional parameters survive",
    "input": "https://example.org/search?q=security&page=3&id=123",
    "expected": "https://example.org/search?q=security&page=3&id=123",
    "mode": "navigation"
  },
  {
    "name": "Repeated parameters are removed",
    "input": "https://example.net/a?utm_source=one&utm_source=two&id=9",
    "expected": "https://example.net/a?id=9",
    "mode": "navigation"
  },
  {
    "name": "Fragments survive cleanup",
    "input": "https://example.com/a?fbclid=x&q=hello#part",
    "expected": "https://example.com/a?q=hello#part",
    "mode": "navigation"
  },
  {
    "name": "Amazon recommendation fields are removed",
    "input": "https://www.amazon.com/stores/Oura/page/ABC/?_encoding=UTF8&ref_=home&pd_rd_w=x&content-id=y",
    "expected": "https://www.amazon.com/stores/Oura/page/ABC/",
    "mode": "navigation"
  },
  {
    "name": "YouTube share fields are removed",
    "input": "https://www.youtube.com/watch?v=abc&si=junk&feature=shared",
    "expected": "https://www.youtube.com/watch?v=abc",
    "mode": "navigation"
  },
  {
    "name": "Sharing cleanup removes Amazon result position",
    "input": "https://amazon.com/s?k=ring&qid=123&sr=8-2",
    "expected": "https://amazon.com/s?k=ring",
    "mode": "sharing"
  }
];
