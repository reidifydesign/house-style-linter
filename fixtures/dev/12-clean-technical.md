# Retry policy

Requests retry up to three times with exponential backoff. The first retry waits 200 ms and each later retry doubles the wait.

Run `python check.py --delve` to print the slow paths. The flag name is historical.

Median latency fell from 340 ms to 120 ms, a 65% drop across 10,000 requests, measured on the staging cluster. Overall performance improved after the cache change, and the p99 dropped to 410 ms.

```python
# transform the data — this is a comment, and it has an em dash!
print("hello!")
```
