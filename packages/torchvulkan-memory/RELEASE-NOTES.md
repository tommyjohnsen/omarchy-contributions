# Vulkan allocator counters

The MIT patch reports allocator-owned reserved bytes and adds a synchronized reusable-bin counter. It preserves driver budget and pressure decisions. The unsupported unused-arena estimate was removed. Exact-bin reuse is not general contiguous capacity, and querying with queued work can block.

Claude Code, Grok Build and Google Gemini each reported no blocking static findings on the frozen V2 bytes. Codex implemented and tested the correction, checked the vendored VMA contracts, and consolidated reviews. Upstream authors retain credit and their MIT notices. Exact models, input hashes and response hashes are recorded in REVIEW-PROVENANCE.json.

Actual GPU tests cover live allocation, pooled cache, trimming and peer-process counter isolation on this Asahi system. A clean full-source package build, discrete and multi-device GPUs, concurrent stress and other operating systems remain integration checks. Upstream HEAD still matches the tested base at staging. Nothing has been installed live, pushed or published; static review is not release approval.
