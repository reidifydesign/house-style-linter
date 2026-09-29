# Cache layer

The cache layer utilizes a robust invalidation scheme to deliver seamless performance. It leverages a write-through policy, which enhances the developer experience.

Benchmarks on the sample dataset show a 6x speedup for repeated reads (see the benchmark notes).

We batch writes. Writes are grouped by 50, which cut commit time from 210 ms to 40 ms.
