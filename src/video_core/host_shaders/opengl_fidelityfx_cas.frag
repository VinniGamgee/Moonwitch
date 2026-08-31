// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#version 460 core

// FidelityFX CAS algorithm adapted from AMD FidelityFX CAS v1.0.
// Copyright (c) 2017-2019 Advanced Micro Devices, Inc. All rights reserved.
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.

layout(location = 0) uniform float sharpness;
layout(binding = 0) uniform sampler2D InputTexture;
layout(location = 0) in vec2 texcoord;
layout(location = 0) out vec4 frag_color;

vec4 CasLoad(ivec2 p) {
    ivec2 size = textureSize(InputTexture, 0);
    return texelFetch(InputTexture, clamp(p, ivec2(0), size - ivec2(1)), 0);
}

vec3 CasFilter(ivec2 p, float amount) {
    vec3 b = CasLoad(p + ivec2( 0, -1)).rgb;
    vec3 d = CasLoad(p + ivec2(-1,  0)).rgb;
    vec3 e = CasLoad(p).rgb;
    vec3 f = CasLoad(p + ivec2( 1,  0)).rgb;
    vec3 h = CasLoad(p + ivec2( 0,  1)).rgb;

    vec3 mn = min(min(min(d, e), f), min(b, h));
    vec3 mx = max(max(max(d, e), f), max(b, h));
    vec3 amp = clamp(min(mn, vec3(1.0) - mx) / max(mx, vec3(1.0e-6)), 0.0, 1.0);
    amp = sqrt(amp);

    float peak = -1.0 / mix(8.0, 5.0, clamp(amount, 0.0, 1.0));
    float w = amp.g * peak;
    float rcp_weight = 1.0 / (1.0 + 4.0 * w);
    return clamp((b * w + d * w + f * w + h * w + e) * rcp_weight, 0.0, 1.0);
}

void main() {
    ivec2 p = ivec2(texcoord * vec2(textureSize(InputTexture, 0)));
    vec4 center = CasLoad(p);
    frag_color = vec4(CasFilter(p, sharpness), center.a);
}
