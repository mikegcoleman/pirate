import pyglet
import math
import os
import random
import time
import ctypes
import ctypes.util

# Helper: Always use ctypes to call OpenGL functions directly for transforms and clearing
opengl_path = ctypes.util.find_library('OpenGL')
if not opengl_path:
    raise ImportError('OpenGL library not found on this system.')
gl_lib = ctypes.cdll.LoadLibrary(opengl_path)
def glBegin(mode): gl_lib.glBegin(mode)
def glEnd(): gl_lib.glEnd()
def glVertex3f(x, y, z): gl_lib.glVertex3f(ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(z))
def glColor3f(r, g, b): gl_lib.glColor3f(ctypes.c_float(r), ctypes.c_float(g), ctypes.c_float(b))
def glPushMatrix(): gl_lib.glPushMatrix()
def glPopMatrix(): gl_lib.glPopMatrix()
def glTranslatef(x, y, z): gl_lib.glTranslatef(ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(z))
def glRotatef(angle, x, y, z): gl_lib.glRotatef(ctypes.c_float(angle), ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(z))
def glScalef(x, y, z): gl_lib.glScalef(ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(z))
def glClear(mask): gl_lib.glClear(mask)
GL_TRIANGLES = 0x0004
GL_COLOR_BUFFER_BIT = 0x00004000
GL_DEPTH_BUFFER_BIT = 0x00000100

# Add OpenGL constants for matrix modes
GL_PROJECTION = 0x1701
GL_MODELVIEW = 0x1700
GL_DEPTH_TEST = 0x0B71

def gluPerspective(fovy, aspect, zNear, zFar):
    fH = math.tan(fovy / 360.0 * math.pi) * zNear
    fW = fH * aspect
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glFrustum(-fW, fW, -fH, fH, zNear, zFar)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def glMatrixMode(mode):
    gl_lib.glMatrixMode(ctypes.c_uint(mode))
def glLoadIdentity():
    gl_lib.glLoadIdentity()
def glFrustum(left, right, bottom, top, zNear, zFar):
    gl_lib.glFrustum(ctypes.c_double(left), ctypes.c_double(right), ctypes.c_double(bottom), ctypes.c_double(top), ctypes.c_double(zNear), ctypes.c_double(zFar))
def glEnable(cap):
    gl_lib.glEnable(ctypes.c_uint(cap))

# Simple OBJ loader for pyglet (supports vertices and faces only)
def load_obj(filename):
    vertices = []
    faces = []
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()
                vertices.append(tuple(map(float, parts[1:4])))
            elif line.startswith('f '):
                parts = line.strip().split()
                face = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                faces.append(face)
    return vertices, faces

# Paths to OBJ files (case-insensitive handling)
BASE_DIR = os.path.dirname(__file__)
OBJ_FILES = {
    'skull': os.path.join(BASE_DIR, 'Skull.obj'),
    'jaw': os.path.join(BASE_DIR, 'Jaw.obj'),
    'upper_teeth': os.path.join(BASE_DIR, 'Upper_teeth.obj'),
    'lower_teeth': os.path.join(BASE_DIR, 'Lower_teeth.obj'),
}

for part, path in OBJ_FILES.items():
    if not os.path.exists(path):
        # Try uppercase extension if not found
        alt_path = path[:-4] + '.OBJ'
        if os.path.exists(alt_path):
            OBJ_FILES[part] = alt_path
        else:
            print(f"ERROR: {part} OBJ file not found at {path} or {alt_path}")
            exit(1)

skull_vertices, skull_faces = load_obj(OBJ_FILES['skull'])
jaw_vertices, jaw_faces = load_obj(OBJ_FILES['jaw'])
upper_teeth_vertices, upper_teeth_faces = load_obj(OBJ_FILES['upper_teeth'])
lower_teeth_vertices, lower_teeth_faces = load_obj(OBJ_FILES['lower_teeth'])

window = pyglet.window.Window(800, 600, caption="Mr. Bones 3D Jaw Test")
rotation = 0.0
jaw_angle = 0.0

# Jaw hinge position (adjust as needed for your model)
JAW_HINGE = [0, -0.2, 0]  # x, y, z

# Animation control
t_start = time.time()


def draw_obj(vertices, faces):
    glBegin(GL_TRIANGLES)
    for face in faces:
        for idx in face:
            glVertex3f(*vertices[idx])
    glEnd()

def draw_skull():
    # Draw skull
    glColor3f(1.0, 1.0, 1.0)
    draw_obj(skull_vertices, skull_faces)
    # Draw upper teeth
    glColor3f(0.9, 0.9, 0.9)
    draw_obj(upper_teeth_vertices, upper_teeth_faces)
    # Draw lower teeth (attached to jaw)
    glPushMatrix()
    glTranslatef(*JAW_HINGE)
    glRotatef(jaw_angle, 1, 0, 0)
    glTranslatef(-JAW_HINGE[0], -JAW_HINGE[1], -JAW_HINGE[2])
    glColor3f(0.9, 0.9, 0.9)
    draw_obj(lower_teeth_vertices, lower_teeth_faces)
    # Draw jaw
    glColor3f(0.8, 0.8, 0.8)
    draw_obj(jaw_vertices, jaw_faces)
    glPopMatrix()

@window.event
def on_draw():
    global rotation
    # Set up projection and enable depth test
    glEnable(GL_DEPTH_TEST)
    gluPerspective(60, window.width / window.height, 0.1, 100.0)
    # Clear the buffer using ctypes OpenGL
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glTranslatef(0, 0, -10)  # Move model further back
    glRotatef(rotation, 0, 1, 0)
    glScalef(1.5, 1.5, 1.5)
    draw_skull()

def update(dt):
    global rotation, jaw_angle
    rotation += 30 * dt  # degrees per second
    # Randomly move jaw every frame for 5 seconds
    if time.time() - t_start < 5:
        jaw_angle = random.uniform(0, 25)
    else:
        jaw_angle = 0  # Close jaw after 5 seconds

pyglet.clock.schedule_interval(update, 1/30.0)

if __name__ == "__main__":
    pyglet.app.run()
