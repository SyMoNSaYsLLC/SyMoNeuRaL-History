// CURRENT CUDA-RUNTIME PCIE CHARACTERIZATION
//
// ============================================================================
// THIS IS NOT A REPRODUCTION OF THE HISTORICAL CuPy TEST.
// ============================================================================
//
// The historical PCIe figures are Grade A and stand unaltered:
//
//     H->D pinned = 6.94 GB/s        (CuPy implementation, 512 MB row)
//     D->H pinned = 7.20 GB/s        (CuPy implementation, 512 MB row)
//
// CuPy is absent from every Python environment on this box (system python3 and
// all four venvs checked), and the `venv-extras` environment that ran the
// historical script no longer exists. Installing CuPy is out of scope, so the
// exact timing and allocation semantics of the historical measurement CANNOT be
// proven equivalent to anything written here.
//
// Therefore the comparison classification is fixed at DIRECTIONAL ONLY, and this
// file must never be used to compute a "regression percentage" against those two
// numbers. What it may legitimately support is a weaker and still useful claim:
// whether the current result is broadly consistent with the physical Gen 3 x8
// link ceiling (7.88 GB/s theoretical).
//
// ============================================================================
// MEASUREMENT DESIGN
// ============================================================================
//
// Bandwidth formula, stated explicitly because the convention matters:
//
//     GB/s = bytes_transferred / elapsed_seconds
//
// ONE WAY. A H2D transfer of N bytes counts N bytes, not 2N. This is the
// opposite convention from a DRAM read+write metric, and conflating the two is
// how a PCIe figure comes to look twice as good as it is. The historical CuPy
// table used the same one-way convention for its H2D/D2H columns (its note
// records that only the D2D column needed the 2x caveat), so the units agree
// even though the implementations do not.
//
// Timing: CUDA events recorded on the stream, around the transfer region only.
// Allocation and free are OUTSIDE the timed region by construction -- buffers are
// allocated before the first event record and freed after the last event query.
// A warm-up transfer runs before timing so first-touch page-table work is not
// billed to the link.
//
// Synchronisation: cudaMemcpyAsync on the default stream, then a single
// cudaEventSynchronize on the stop event. The loop is submitted without
// per-iteration host sync so the link stays saturated; correctness of the timing
// rests on the stop event being ordered after every copy in the stream.
//
// Iterations: >= 10 recorded per direction, each timed individually so a real
// distribution can be reported rather than one aggregate. The 512 MiB primary
// size is large enough that per-transfer overhead is negligible against a
// ~70 ms transfer.
//
// Sustained mode: because a single 512 MiB copy completes in well under a
// second, an external nvidia-smi poll can easily miss the negotiated link state.
// Passing --sustain <seconds> keeps transfers in flight continuously so the link
// can be observed under real load.

#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>

#define CHECK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) {              \
    fprintf(stderr, "CUDA error: %s (%s:%d)\n", cudaGetErrorString(e_),           \
            __FILE__, __LINE__); exit(1); } } while (0)

struct Stats {
    double mean, median, min, max, sd, cov;
};

static Stats stats_of(std::vector<double> v) {
    Stats s{};
    if (v.empty()) return s;
    std::sort(v.begin(), v.end());
    s.min = v.front();
    s.max = v.back();
    size_t n = v.size();
    s.median = (n % 2) ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
    double sum = 0.0;
    for (double x : v) sum += x;
    s.mean = sum / n;
    if (n > 1) {
        double ss = 0.0;
        for (double x : v) ss += (x - s.mean) * (x - s.mean);
        s.sd = std::sqrt(ss / (n - 1));          // sample stdev
    }
    s.cov = (s.mean != 0.0) ? (s.sd / s.mean * 100.0) : 0.0;
    return s;
}

// One timed transfer. Allocation is the caller's job and is never timed here.
static double one_transfer_gbps(void *dst, const void *src, size_t bytes,
                                cudaMemcpyKind kind,
                                cudaEvent_t start, cudaEvent_t stop) {
    CHECK(cudaEventRecord(start));
    CHECK(cudaMemcpyAsync(dst, src, bytes, kind));
    CHECK(cudaEventRecord(stop));
    CHECK(cudaEventSynchronize(stop));
    float ms = 0.0f;
    CHECK(cudaEventElapsedTime(&ms, start, stop));
    // ONE WAY: bytes / seconds. Decimal GB, matching the historical table.
    return (double)bytes / (ms / 1000.0) / 1e9;
}

static void report(const char *label, size_t bytes, const std::vector<double> &v) {
    Stats s = stats_of(v);
    printf("\n[%s]  size=%zu MiB  iterations=%zu\n",
           label, bytes / (1024 * 1024), v.size());
    printf("  per-iteration GB/s:");
    for (size_t i = 0; i < v.size(); ++i) {
        if (i % 5 == 0) printf("\n   ");
        printf(" %8.3f", v[i]);
    }
    printf("\n  mean   %8.4f GB/s\n", s.mean);
    printf("  median %8.4f GB/s\n", s.median);
    printf("  min    %8.4f GB/s\n", s.min);
    printf("  max    %8.4f GB/s\n", s.max);
    printf("  stdev  %8.4f GB/s\n", s.sd);
    printf("  CoV    %8.4f %%\n", s.cov);
}

int main(int argc, char **argv) {
    size_t primary_mib = 512;
    int iters = 12;
    double sustain_s = 0.0;

    for (int i = 1; i < argc; ++i) {
        if (!strncmp(argv[i], "--size-mib=", 11))  primary_mib = strtoull(argv[i] + 11, nullptr, 10);
        else if (!strncmp(argv[i], "--iters=", 8)) iters = atoi(argv[i] + 8);
        else if (!strncmp(argv[i], "--sustain=", 10)) sustain_s = atof(argv[i] + 10);
    }

    cudaDeviceProp p;
    CHECK(cudaGetDeviceProperties(&p, 0));

    printf("=== CURRENT CUDA-RUNTIME PCIE CHARACTERIZATION ===\n");
    printf("NOT a reproduction of the historical CuPy test. Comparison is DIRECTIONAL ONLY.\n");
    printf("Historical (Grade A, CuPy, unaltered): H2D pinned 6.94 GB/s, D2H pinned 7.20 GB/s\n\n");
    printf("Device: %s\n", p.name);
    printf("Compute capability: %d.%d\n", p.major, p.minor);
    printf("Memory bus width: %d-bit\n", p.memoryBusWidth);
    printf("L2 cache: %d bytes\n", p.l2CacheSize);
    printf("Implementation: CUDA Runtime API, cudaHostAlloc + cudaMemcpyAsync, CUDA events\n");
    printf("Bandwidth formula: bytes / elapsed_seconds  (ONE WAY, not read+write)\n");

    const size_t bytes = primary_mib * 1024ull * 1024ull;

    // --- allocate everything up front; none of this is inside a timed region ---
    void *d = nullptr;
    CHECK(cudaMalloc(&d, bytes));

    void *h_pin = nullptr;
    CHECK(cudaHostAlloc(&h_pin, bytes, cudaHostAllocDefault));   // page-locked
    void *h_page = malloc(bytes);                                 // pageable
    if (!h_page) { fprintf(stderr, "pageable host alloc failed\n"); return 1; }

    memset(h_pin, 1, bytes);
    memset(h_page, 1, bytes);

    cudaEvent_t start, stop;
    CHECK(cudaEventCreate(&start));
    CHECK(cudaEventCreate(&stop));

    // --- sustained mode: keep the link busy so an external poll can see it ---
    if (sustain_s > 0.0) {
        printf("\n--- SUSTAINED TRANSFER for %.1f s (for external PCIe link sampling) ---\n",
               sustain_s);
        fflush(stdout);
        cudaEvent_t t0, t1;
        CHECK(cudaEventCreate(&t0));
        CHECK(cudaEventCreate(&t1));
        CHECK(cudaEventRecord(t0));
        double elapsed = 0.0;
        long long n = 0;
        while (elapsed < sustain_s * 1000.0) {
            for (int k = 0; k < 8; ++k) {
                CHECK(cudaMemcpyAsync(d, h_pin, bytes, cudaMemcpyHostToDevice));
                CHECK(cudaMemcpyAsync(h_pin, d, bytes, cudaMemcpyDeviceToHost));
                n += 2;
            }
            CHECK(cudaEventRecord(t1));
            CHECK(cudaEventSynchronize(t1));
            float ms = 0.0f;
            CHECK(cudaEventElapsedTime(&ms, t0, t1));
            elapsed = ms;
        }
        printf("  sustained %lld transfers over %.2f s\n", n, elapsed / 1000.0);
        CHECK(cudaEventDestroy(t0));
        CHECK(cudaEventDestroy(t1));
    }

    // --- warm-up, then the recorded iterations, per direction -----------------
    // Warm-up is deliberately outside the recorded set.
    CHECK(cudaMemcpy(d, h_pin, bytes, cudaMemcpyHostToDevice));
    CHECK(cudaMemcpy(h_pin, d, bytes, cudaMemcpyDeviceToHost));
    CHECK(cudaDeviceSynchronize());

    std::vector<double> h2d_pin, d2h_pin, h2d_page, d2h_page;

    for (int i = 0; i < iters; ++i)
        h2d_pin.push_back(one_transfer_gbps(d, h_pin, bytes, cudaMemcpyHostToDevice, start, stop));
    for (int i = 0; i < iters; ++i)
        d2h_pin.push_back(one_transfer_gbps(h_pin, d, bytes, cudaMemcpyDeviceToHost, start, stop));

    // Pageable is optional current characterisation, reported separately so it
    // cannot be mistaken for the pinned figure the historical table used.
    for (int i = 0; i < iters; ++i)
        h2d_page.push_back(one_transfer_gbps(d, h_page, bytes, cudaMemcpyHostToDevice, start, stop));
    for (int i = 0; i < iters; ++i)
        d2h_page.push_back(one_transfer_gbps(h_page, d, bytes, cudaMemcpyDeviceToHost, start, stop));

    report("H2D PINNED  (primary)", bytes, h2d_pin);
    report("D2H PINNED  (primary)", bytes, d2h_pin);
    report("H2D pageable (optional)", bytes, h2d_page);
    report("D2H pageable (optional)", bytes, d2h_page);

    Stats sh = stats_of(h2d_pin), sd = stats_of(d2h_pin);
    const double gen3x8_theoretical = 7.88;   // GB/s, from the historical dossier
    printf("\n--- consistency with the physical link ceiling ---\n");
    printf("Gen 3 x8 theoretical: %.2f GB/s\n", gen3x8_theoretical);
    printf("H2D pinned mean is %.1f%% of that ceiling\n", sh.mean / gen3x8_theoretical * 100.0);
    printf("D2H pinned mean is %.1f%% of that ceiling\n", sd.mean / gen3x8_theoretical * 100.0);
    printf("\nNOTE: no regression percentage against the historical CuPy figures is\n");
    printf("computed here, deliberately. The implementations are not equivalent.\n");

    CHECK(cudaEventDestroy(start));
    CHECK(cudaEventDestroy(stop));
    CHECK(cudaFreeHost(h_pin));
    free(h_page);
    CHECK(cudaFree(d));

    printf("\nDone. No model was loaded and no engine was started.\n");
    return 0;
}
