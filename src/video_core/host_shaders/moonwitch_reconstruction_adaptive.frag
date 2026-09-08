// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-FileCopyrightText: Copyright (c) 2025, Qualcomm Innovation Center, Inc. All rights reserved.
// SPDX-License-Identifier: BSD-3-Clause

#version 460 core

// Moonwitch Reconstruction Stage 3.
// Derived from Qualcomm SGSR1 edge-direction reconstruction. This variant keeps the same
// one-pass sampling footprint, then adapts the correction strength using data already gathered
// by the edge filter. Flat/bright regions are protected while real texture/geometry edges retain
// most of the reconstruction strength.

// Operation modes: RGBA -> 1, RGBY -> 3, LERP -> 4
#define OperationMode 1
#define EdgeThreshold 8.0/255.0

layout( push_constant ) uniform constants {
    vec4 ViewportInfo[1];
    vec2 ResizeFactor;
    vec2 CropOffset;
    float EdgeSharpness;
};
layout(set = 0, binding = 0) uniform sampler2D ps0;
layout(location=0) in vec2 in_TEXCOORD0;
layout(location=0) out vec4 out_Target0;

float fastLanczos2(float x) {
    float wA = x-4.0;
    float wB = x*wA-wA;
    wA *= wA;
    return wB*wA;
}

vec2 weightY(float dx, float dy, float c, vec3 data) {
    float std = data.x;
    vec2 dir = data.yz;
    float edgeDis = ((dx*dir.y)+(dy*dir.x));
    float x = (((dx*dx)+(dy*dy))+((edgeDis*edgeDis)*((clamp(((c*c)*std),0.0,1.0)*0.7)+-1.0)));
    float w = fastLanczos2(x);
    return vec2(w, w * c);
}

vec2 edgeDirection(vec4 left, vec4 right) {
    vec2 dir;
    float RxLz = (right.x + (-left.z));
    float RwLy = (right.w + (-left.y));
    vec2 delta;
    delta.x = (RxLz + RwLy);
    delta.y = (RxLz + (-RwLy));
    float lengthInv = inversesqrt((delta.x * delta.x+ 3.075740e-05) + (delta.y * delta.y));
    dir.x = (delta.x * lengthInv);
    dir.y = (delta.y * lengthInv);
    return dir;
}

float moonwitchAdaptiveStrength(vec3 sourceColor, float localRange, float edgeVote) {
    // Keep smooth gradients (sky, fog and bloom) quiet. Fine texture ramps up progressively
    // instead of crossing a hard sharpening threshold.
    float detailConfidence = smoothstep(2.0 / 255.0, 22.0 / 255.0, localRange);
    float edgeConfidence = smoothstep(EdgeThreshold, 36.0 / 255.0, edgeVote);

    float luminance = dot(sourceColor, vec3(0.2126, 0.7152, 0.0722));
    float flatness = 1.0 - detailConfidence;
    float highlightMask = smoothstep(0.72, 0.98, luminance) * flatness;

    float detailStrength = mix(0.18, 1.0, detailConfidence);
    float edgeStrength = mix(0.62, 1.0, edgeConfidence);
    float highlightProtection = mix(1.0, 0.40, highlightMask);

    // Strong silhouettes already carry plenty of contrast. Back off slightly there to reduce
    // halos/ringing while preserving the actual edge location.
    float highContrastProtection = mix(1.0, 0.78, smoothstep(0.20, 0.45, localRange));

    return clamp(detailStrength * edgeStrength * highlightProtection * highContrastProtection,
                 0.12, 1.0);
}

void main() {
    vec4 color;
    if(OperationMode == 1)
        color.xyz = textureLod(ps0, in_TEXCOORD0.xy, 0.0).xyz;
    else
        color.xyzw = textureLod(ps0, in_TEXCOORD0.xy, 0.0).xyzw;

    vec3 sourceColor = color.xyz;

    if ( OperationMode!=4) {
        vec2 imgCoord = ((in_TEXCOORD0.xy*ViewportInfo[0].zw)+vec2(-0.5,0.5));
        vec2 imgCoordPixel = floor(imgCoord);
        vec2 coord = (imgCoordPixel*ViewportInfo[0].xy);
        vec2 pl = imgCoord - imgCoordPixel;
        vec4  left = textureGather(ps0, coord, OperationMode);
        float edgeVote = abs(left.z - left.y) + abs(color[OperationMode] - left.y)  + abs(color[OperationMode] - left.z) ;
        if(edgeVote > EdgeThreshold) {
            coord.x += ViewportInfo[0].x;

            vec2 IR_highp_vec2_0 = coord + vec2(ViewportInfo[0].x, 0.0);
            vec4 right = textureGather(ps0, IR_highp_vec2_0, OperationMode);
            vec4 upDown;
            vec2 IR_highp_vec2_1 = coord + vec2(0.0, -ViewportInfo[0].y);
            upDown.xy = textureGather(ps0, IR_highp_vec2_1, OperationMode).wz;
            vec2 IR_highp_vec2_2 = coord + vec2(0.0, ViewportInfo[0].y);
            upDown.zw  = textureGather(ps0, IR_highp_vec2_2, OperationMode).yx;

            float mean = (left.y+left.z+right.x+right.w)*0.25;
            left = left - vec4(mean);
            right = right - vec4(mean);
            upDown = upDown - vec4(mean);
            color.w =color[OperationMode] - mean;

            float sum = (((((abs(left.x)+abs(left.y))+abs(left.z))+abs(left.w))+(((abs(right.x)+abs(right.y))+abs(right.z))+abs(right.w)))+(((abs(upDown.x)+abs(upDown.y))+abs(upDown.z))+abs(upDown.w)));
            float sumMean = 1.014185e+01/sum;
            float std = (sumMean*sumMean);

            vec3 data = vec3(std, edgeDirection(left, right));
            vec2 aWY = weightY(pl.x, pl.y+1.0, upDown.x,data);
            aWY += weightY(pl.x-1.0, pl.y+1.0, upDown.y,data);
            aWY += weightY(pl.x-1.0, pl.y-2.0, upDown.z,data);
            aWY += weightY(pl.x, pl.y-2.0, upDown.w,data);
            aWY += weightY(pl.x+1.0, pl.y-1.0, left.x,data);
            aWY += weightY(pl.x, pl.y-1.0, left.y,data);
            aWY += weightY(pl.x, pl.y, left.z,data);
            aWY += weightY(pl.x+1.0, pl.y, left.w,data);
            aWY += weightY(pl.x-1.0, pl.y-1.0, right.x,data);
            aWY += weightY(pl.x-2.0, pl.y-1.0, right.y,data);
            aWY += weightY(pl.x-2.0, pl.y, right.z,data);
            aWY += weightY(pl.x-1.0, pl.y, right.w,data);

            float finalY = aWY.y/aWY.x;
            float maxY = max(max(left.y,left.z),max(right.x,right.w));
            float minY = min(min(left.y,left.z),min(right.x,right.w));
            float deltaY = clamp(EdgeSharpness*finalY, minY, maxY) -color.w;

            // Preserve SGSR's local clamp, then make the correction content-aware. Stage 3 adds
            // arithmetic only; it does not add another texture pass or extra texture samples.
            deltaY = clamp(deltaY, -23.0 / 255.0, 23.0 / 255.0);
            float localRange = maxY - minY;
            deltaY *= moonwitchAdaptiveStrength(sourceColor, localRange, edgeVote);

            color.x = clamp((color.x+deltaY),0.0,1.0);
            color.y = clamp((color.y+deltaY),0.0,1.0);
            color.z = clamp((color.z+deltaY),0.0,1.0);
        }
    }
    color.w = 1.0;  //assume alpha channel is not used
    out_Target0.xyzw = color;
}
