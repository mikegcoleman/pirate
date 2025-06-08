import pyglet
from pyglet.gl import glBegin, glEnd, glVertex3f, glColor3f, glPushMatrix, glPopMatrix, glTranslatef, glRotatef, glScalef, glLoadIdentity, GL_TRIANGLES
import math
import os

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

# Paths to OBJ files
BASE_DIR = os.path.dirname(__file__)
OBJ_FILES = {
    'skull': os.path.join(BASE_DIR, 'Skull.obj'),
    'jaw': os.path.join(BASE_DIR, 'Jaw.obj'),
    'upper_teeth': os.path.join(BASE_DIR, 'Upper_teeth.obj'),
    'lower_teeth': os.path.join(BASE_DIR, 'Lower_teeth.obj'),
}

for part, path in OBJ_FILES.items():
    if not os.path.exists(path):
        print(f"ERROR: {part} OBJ file not found at {path}")
        exit(1)

skull_vertices, skull_faces = load_obj(OBJ_FILES['skull'])
jaw_vertices, jaw_faces = load_obj(OBJ_FILES['jaw'])
upper_teeth_vertices, upper_teeth_faces = load_obj(OBJ_FILES['upper_teeth'])
lower_teeth_vertices, lower_teeth_faces = load_obj(OBJ_FILES['lower_teeth'])

window = pyglet.window.Window(800, 600, caption="Mr. Bones 3D Skull")
rotation = 0.0
jaw_angle = 0.0
jaw_opening = True

# Jaw hinge position (adjust as needed for your model)
JAW_HINGE = [0, -0.2, 0]  # x, y, z


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
    window.clear()
    glLoadIdentity()
    glTranslatef(0, 0, -5)
    glRotatef(rotation, 0, 1, 0)
    glScalef(1.5, 1.5, 1.5)
    draw_skull()

def update(dt):
    global rotation, jaw_angle, jaw_opening
    rotation += 30 * dt  # degrees per second
    # Animate jaw open/close
    if jaw_opening:
        jaw_angle += 30 * dt
        if jaw_angle > 25:
            jaw_opening = False
    else:
        jaw_angle -= 30 * dt
        if jaw_angle < 0:
            jaw_opening = True

pyglet.clock.schedule_interval(update, 1/60.0)

if __name__ == "__main__":
    pyglet.app.run()
