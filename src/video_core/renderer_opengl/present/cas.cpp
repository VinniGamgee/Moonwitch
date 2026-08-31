// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <algorithm>

#include "common/moonwitch_cas_settings.h"
#include "video_core/host_shaders/full_screen_triangle_vert.h"
#include "video_core/host_shaders/opengl_fidelityfx_cas_frag.h"
#include "video_core/renderer_opengl/gl_shader_manager.h"
#include "video_core/renderer_opengl/gl_shader_util.h"
#include "video_core/renderer_opengl/present/cas.h"
#include "video_core/renderer_opengl/present/util.h"

namespace OpenGL {

CAS::CAS(u32 width_, u32 height_) : width{width_}, height{height_} {
    vert = CreateProgram(HostShaders::FULL_SCREEN_TRIANGLE_VERT, GL_VERTEX_SHADER);
    frag = CreateProgram(HostShaders::OPENGL_FIDELITYFX_CAS_FRAG, GL_FRAGMENT_SHADER);

    glProgramUniform2f(vert.handle, 0, 1.0f, -1.0f);
    glProgramUniform2f(vert.handle, 1, 0.0f, 1.0f);

    sampler = CreateNearestNeighborSampler();
    framebuffer.Create();
    texture.Create(GL_TEXTURE_2D);
    glTextureStorage2D(texture.handle, 1, GL_RGBA16F, static_cast<GLsizei>(width),
                       static_cast<GLsizei>(height));
}

CAS::~CAS() = default;

GLuint CAS::Draw(ProgramManager& program_manager, GLuint source_texture) {
    const float sharpness = std::clamp(static_cast<float>(Settings::GetCasSharpness()) / 100.0f,
                                       0.0f, 1.0f);
    glProgramUniform1f(frag.handle, 0, sharpness);

    glFrontFace(GL_CW);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, framebuffer.handle);
    glNamedFramebufferTexture(framebuffer.handle, GL_COLOR_ATTACHMENT0, texture.handle, 0);
    glViewportIndexedf(0, 0.0f, 0.0f, static_cast<GLfloat>(width), static_cast<GLfloat>(height));
    program_manager.BindPresentPrograms(vert.handle, frag.handle);
    glBindTextureUnit(0, source_texture);
    glBindSampler(0, sampler.handle);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    return texture.handle;
}

bool CAS::NeedsRecreation(u32 new_width, u32 new_height) const {
    return new_width != width || new_height != height;
}

} // namespace OpenGL
