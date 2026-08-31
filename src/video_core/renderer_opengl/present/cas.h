// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "common/common_types.h"
#include "video_core/renderer_opengl/gl_resource_manager.h"

namespace OpenGL {

class ProgramManager;

class CAS final {
public:
    explicit CAS(u32 width, u32 height);
    ~CAS();

    GLuint Draw(ProgramManager& program_manager, GLuint texture);
    [[nodiscard]] bool NeedsRecreation(u32 width, u32 height) const;

private:
    u32 width{};
    u32 height{};
    OGLFramebuffer framebuffer;
    OGLSampler sampler;
    OGLProgram vert;
    OGLProgram frag;
    OGLTexture texture;
};

} // namespace OpenGL
