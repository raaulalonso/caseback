#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

// Onboarding blob field (the design notes section 10, decision D30).
//
// Seven signed-distance shapes joined by a smooth union so neighbours fuse like drops. Flat colour: each pixel takes the
// colour of the nearest blob, with a narrow blend only where two blobs are fusing. No blur, no glow, no gradient.
// Edges are anti-aliased by distance. Everything is in points.

constant int kStride = 12;  // x, y, r, morph, kind, rotation, wobble, red, green, blue, stretch, stretchAngle

static float sdTriangleUp(float2 p, float r) {
    // Equilateral triangle, half side r, apex up (screen y grows downwards, so flip).
    p.y = -p.y;
    const float k = 1.7320508;
    p.x = abs(p.x) - r;
    p.y = p.y + r / k;
    if (p.x + k * p.y > 0.0) {
        p = float2(p.x - k * p.y, -k * p.x - p.y) * 0.5;
    }
    p.x -= clamp(p.x, -2.0 * r, 0.0);
    return -length(p) * sign(p.y);
}

static float sdBox(float2 p, float2 h) {
    float2 q = abs(p) - h;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
}

// Distance to the mark of a given kind: 0 circle, 1 diamond, 2 square, 3 triangle up, 4 open circle,
// 5 triangle down, 6 bar. Sizes are tuned so every mark has about the same visual weight.
static float sdMark(float2 p, float r, int kind) {
    switch (kind) {
        case 1: return (abs(p.x) + abs(p.y) - r * 1.12) * 0.70710678;
        case 2: return sdBox(p, float2(r * 0.80)) - 1.5;
        case 3: return sdTriangleUp(p + float2(0.0, r * 0.12), r * 0.92) - 1.0;
        case 4: return abs(length(p) - r * 0.70) - r * 0.22;
        case 5: return sdTriangleUp(float2(p.x, -p.y) + float2(0.0, r * 0.12), r * 0.92) - 1.0;
        case 6: return sdBox(p, float2(r * 0.30, r * 1.05)) - 1.5;
        default: return length(p) - r;
    }
}

[[ stitchable ]] half4 blobField(float2 position, half4 currentColor,
                                 float2 size, float time,
                                 device const float *blobs, int count,
                                 float smoothness) {
    float dist[8];
    float3 col[8];
    int n = min(count / kStride, 8);
    float dmin = 1.0e9;

    for (int i = 0; i < n; i++) {
        device const float *b = blobs + i * kStride;
        float2 c = float2(b[0], b[1]);
        float r = b[2];
        float morph = b[3];
        int kind = int(b[4] + 0.5);
        float rot = b[5];
        float wobble = b[6];

        float2 p = position - c;

        // Squash and stretch: elongate along the direction of travel, thin across it (volume roughly kept).
        float stretch = b[10];
        if (stretch > 0.001) {
            float sa = b[11];
            float c1 = cos(sa), s1 = sin(sa);
            float2 q = float2(c1 * p.x + s1 * p.y, -s1 * p.x + c1 * p.y);
            q.x /= (1.0 + stretch);
            q.y *= (1.0 + 0.7 * stretch);
            p = float2(c1 * q.x - s1 * q.y, s1 * q.x + c1 * q.y);
        }

        float cs = cos(rot), sn = sin(rot);
        p = float2(cs * p.x + sn * p.y, -sn * p.x + cs * p.y);

        // Organic wobble of the blob outline; it fades out as the shape becomes a mark.
        float a = atan2(p.y, p.x);
        float ph = float(i) * 1.7;
        float wob = wobble * (0.70 * sin(3.0 * a + time * 0.9 + ph) + 0.30 * sin(5.0 * a - time * 1.3 + ph * 2.0));
        float blob = length(p) - r * (1.0 + wob);

        float d = (morph <= 0.001) ? blob : mix(blob, sdMark(p, r, kind), clamp(morph, 0.0, 1.0));
        dist[i] = d;
        col[i] = float3(b[7], b[8], b[9]);
        dmin = min(dmin, d);
    }

    // Smooth union of the distances; colour weights are sharper than the shape blend so colours stay flat.
    float k = max(smoothness, 0.5);
    float kc = 0.15;  // colour switches over a couple of points: flat fills with a crisp edge
    float sum = 0.0, wsum = 0.0;
    float3 mixed = float3(0.0);
    for (int i = 0; i < n; i++) {
        sum += exp(-(dist[i] - dmin) / k);
        float w = exp(-(dist[i] - dmin) / kc);
        wsum += w;
        mixed += col[i] * w;
    }
    float d = dmin - k * log(max(sum, 1.0e-6));
    float3 rgb = mixed / max(wsum, 1.0e-6);

    float alpha = 1.0 - smoothstep(-0.6, 0.6, d);
    // Premultiplied, transparent outside the blobs, so a ruler or text can sit behind the field.
    return half4(half3(rgb * alpha), half(alpha));
}
