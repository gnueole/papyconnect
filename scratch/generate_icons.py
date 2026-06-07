import os
import math

def create_bmp(width, height, draw_func, filename):
    pixel_data_size = width * height * 3
    file_size = 54 + pixel_data_size
    
    header = bytearray(54)
    # File Header
    header[0:2] = b'BM'
    header[2:6] = file_size.to_bytes(4, 'little')
    header[10:14] = int(54).to_bytes(4, 'little')
    
    # DIB Header
    header[14:18] = int(40).to_bytes(4, 'little')
    header[18:22] = width.to_bytes(4, 'little')
    header[22:26] = height.to_bytes(4, 'little')
    header[26:28] = int(1).to_bytes(2, 'little')
    header[28:30] = int(24).to_bytes(2, 'little')
    header[34:38] = pixel_data_size.to_bytes(4, 'little')
    
    pixels = bytearray(pixel_data_size)
    draw_func(width, height, pixels)
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(header)
        f.write(pixels)
    print(f"Generated {filename}")

# Helper drawing functions
def get_draw_helpers(width, height, pixels):
    def set_pixel(x, y, color):
        if 0 <= x < width and 0 <= y < height:
            idx = ((height - 1 - y) * width + x) * 3
            pixels[idx] = int(color[2]) # B
            pixels[idx+1] = int(color[1]) # G
            pixels[idx+2] = int(color[0]) # R

    def fill_all(color):
        for y in range(height):
            for x in range(width):
                set_pixel(x, y, color)

    def draw_rect(x1, y1, x2, y2, color, fill=False, thickness=1):
        if fill:
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    set_pixel(x, y, color)
        else:
            for t in range(thickness):
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    set_pixel(x, y1 + t, color)
                    set_pixel(x, y2 - t, color)
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    set_pixel(x1 + t, y, color)
                    set_pixel(x2 - t, y, color)

    def draw_circle(cx, cy, r, color, fill=False, thickness=1):
        if fill:
            for y in range(max(0, cy - r), min(height, cy + r + 1)):
                for x in range(max(0, cx - r), min(width, cx + r + 1)):
                    if (x - cx)**2 + (y - cy)**2 <= r**2:
                        set_pixel(x, y, color)
        else:
            # Draw circles of different radii for thickness
            for t in range(thickness):
                cur_r = r - t
                if cur_r < 0: continue
                # Midpoint circle algorithm
                x = cur_r
                y = 0
                err = 0
                while x >= y:
                    set_pixel(cx + x, cy + y, color)
                    set_pixel(cx + y, cy + x, color)
                    set_pixel(cx - y, cy + x, color)
                    set_pixel(cx - x, cy + y, color)
                    set_pixel(cx - x, cy - y, color)
                    set_pixel(cx - y, cy - x, color)
                    set_pixel(cx + y, cy - x, color)
                    set_pixel(cx + x, cy - y, color)
                    y += 1
                    err += 1 + 2*y
                    if 2*(err - x) + 1 > 0:
                        x -= 1
                        err += 1 - 2*x

    def draw_thick_line(x1, y1, x2, y2, color, thickness=1):
        # Using a simple line drawer that brushes with a circle
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx*dx + dy*dy)
        steps = int(max(distance, 1))
        for i in range(steps + 1):
            t = i / steps
            x = int(x1 + dx * t)
            y = int(y1 + dy * t)
            # Draw brush
            if thickness == 1:
                set_pixel(x, y, color)
            else:
                br = int(thickness / 2)
                for bx in range(-br, br + 1):
                    for by in range(-br, br + 1):
                        if bx*bx + by*by <= br*br:
                            set_pixel(x + bx, y + by, color)

    return set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line


# ── Icon Creators ──────────────────────────────────────────────────────────

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (29, 185, 84)       # Spotify
RED = (229, 9, 20)          # Netflix / Youtube
BLUE = (0, 168, 232)         # Disney (light blue)
LIGHT_BLUE = (0, 99, 229)  # Amazon (dark blue)
PURPLE = (130, 0, 255)      # TV / Ampli / Default

def draw_spotify(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = GREEN if active else BLACK
    fg = BLACK if active else GREEN
    
    fill_all(bg)
    
    cx, cy = w // 2, h // 2
    r = int(w * 0.35)
    draw_circle(cx, cy, r, fg, thickness=2)
    
    # 3 Spotify waves (curved arcs)
    for dx_val in range(-int(r*0.6), int(r*0.6) + 1):
        dx = float(dx_val)
        # Curved/tilted wave equation: y = base_y + dx * tilt + dx^2 * curve
        # Top wave
        y1 = (cy - r * 0.3) + (dx * -0.12) + (dx * dx * 0.012)
        # Mid wave
        y2 = cy + (dx * -0.12) + (dx * dx * 0.012)
        # Bot wave
        y3 = (cy + r * 0.3) + (dx * -0.12) + (dx * dx * 0.012)
        
        # Render them with appropriate thickness
        for t in range(-1, 2):
            set_pixel(int(cx + dx), int(y1 + t), fg)
            set_pixel(int(cx + dx), int(y2 + t), fg)
            set_pixel(int(cx + dx), int(y3 + t), fg)

def draw_netflix(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = RED if active else BLACK
    fg = BLACK if active else RED
    
    fill_all(bg)
    
    # Draw Bold 'N'
    leftX = w * 0.32
    rightX = w * 0.68
    topY = h * 0.22
    bottomY = h * 0.78
    thick = int(w * 0.1)
    
    # Left ribbon
    draw_rect(int(leftX), int(topY), int(leftX + thick), int(bottomY), fg, fill=True)
    # Right ribbon
    draw_rect(int(rightX - thick), int(topY), int(rightX), int(bottomY), fg, fill=True)
    # Diagonal ribbon
    draw_thick_line(int(leftX + thick/2), int(topY), int(rightX - thick/2), int(bottomY), fg, thickness=thick)

def draw_youtube(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = RED if active else BLACK
    fg = BLACK if active else RED
    
    fill_all(bg)
    
    # YouTube Rectangle
    rectW = int(w * 0.62)
    rectH = int(h * 0.44)
    rectX = (w - rectW) // 2
    rectY = (h - rectH) // 2
    draw_rect(rectX, rectY, rectX + rectW, rectY + rectH, fg, fill=True)
    
    # Play triangle in center pointing right (needs to be BG color)
    triColor = bg
    triStartX = w // 2 - int(w * 0.08)
    triEndX = w // 2 + int(w * 0.11)
    triCenterY = h // 2
    triHalfHeight = int(h * 0.11)
    
    for x in range(triStartX, triEndX + 1):
        dy = triHalfHeight - (x - triStartX) * triHalfHeight // (triEndX - triStartX + 1)
        draw_thick_line(x, triCenterY - dy, x, triCenterY + dy, triColor, thickness=1)

def draw_disney(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = BLUE if active else BLACK
    fg = BLACK if active else BLUE
    
    fill_all(bg)
    
    # Mickey Mouse shape
    centerX = w // 2
    centerY = h // 2 + int(h * 0.05)
    headRadius = int(w * 0.22)
    earRadius = int(w * 0.13)
    earOffset = int(w * 0.19)
    
    draw_circle(centerX, centerY, headRadius, fg, fill=True)
    draw_circle(centerX - earOffset, centerY - earOffset, earRadius, fg, fill=True)
    draw_circle(centerX + earOffset, centerY - earOffset, earRadius, fg, fill=True)

def draw_amazon(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = LIGHT_BLUE if active else BLACK
    fg = BLACK if active else LIGHT_BLUE
    
    fill_all(bg)
    
    # Bold A shape
    topX = w // 2
    bottomY = int(h * 0.75)
    thick = int(w * 0.1)
    
    # Left leg
    draw_thick_line(topX, int(h * 0.25), int(w * 0.28), bottomY, fg, thickness=thick)
    # Right leg
    draw_thick_line(topX, int(h * 0.25), int(w * 0.72), bottomY, fg, thickness=thick)
    # Crossbar
    draw_thick_line(int(w * 0.38), int(h * 0.58), int(w * 0.62), int(h * 0.58), fg, thickness=thick-2)

def draw_tv(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = PURPLE if active else BLACK
    fg = BLACK if active else PURPLE
    
    fill_all(bg)
    
    # TV frame
    rx1 = int(w * 0.2)
    rx2 = int(w * 0.8)
    ry1 = int(h * 0.3)
    ry2 = int(h * 0.7)
    draw_rect(rx1, ry1, rx2, ry2, fg, thickness=2)
    
    # Screen outline
    draw_rect(rx1 + 3, ry1 + 3, rx2 - 3, ry2 - 3, fg, thickness=1)
    
    # TV stand
    cx = w // 2
    draw_thick_line(cx, ry2, cx, ry2 + 5, fg, thickness=3)
    draw_thick_line(cx - 10, ry2 + 5, cx + 10, ry2 + 5, fg, thickness=3)
    
    # TV antennas
    draw_thick_line(cx, ry1, cx - 12, ry1 - 10, fg, thickness=2)
    draw_thick_line(cx, ry1, cx + 12, ry1 - 10, fg, thickness=2)

def draw_amplifier(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = PURPLE if active else BLACK
    fg = BLACK if active else PURPLE
    
    fill_all(bg)
    
    # Receiver box
    rx1 = int(w * 0.15)
    rx2 = int(w * 0.85)
    ry1 = int(h * 0.35)
    ry2 = int(h * 0.65)
    draw_rect(rx1, ry1, rx2, ry2, fg, thickness=2)
    
    # Volume dial left, selector right
    draw_circle(rx1 + 10, ry1 + 10, 6, fg, thickness=2)
    draw_circle(rx2 - 10, ry1 + 10, 6, fg, thickness=2)
    
    # LED Display in middle
    draw_rect(rx1 + 22, ry1 + 6, rx2 - 22, ry2 - 6, fg, thickness=1)
    # Sound wave indicator inside LED
    draw_thick_line(w // 2 - 10, h // 2, w // 2 - 10, h // 2 + 3, fg, thickness=1)
    draw_thick_line(w // 2 - 5, h // 2 - 2, w // 2 - 5, h // 2 + 4, fg, thickness=1)
    draw_thick_line(w // 2, h // 2 - 4, w // 2, h // 2 + 5, fg, thickness=1)
    draw_thick_line(w // 2 + 5, h // 2 - 2, w // 2 + 5, h // 2 + 4, fg, thickness=1)
    draw_thick_line(w // 2 + 10, h // 2, w // 2 + 10, h // 2 + 3, fg, thickness=1)

def draw_default(w, h, pixels, active=False):
    set_pixel, fill_all, draw_rect, draw_circle, draw_thick_line = get_draw_helpers(w, h, pixels)
    bg = PURPLE if active else BLACK
    fg = BLACK if active else PURPLE
    
    fill_all(bg)


def main():
    target_dir = "papiconnect/app/static/icons"
    os.makedirs(target_dir, exist_ok=True)
    
    icons = {
        "spotify": draw_spotify,
        "netflix": draw_netflix,
        "youtube": draw_youtube,
        "disney_plus": draw_disney,
        "amazon": draw_amazon,
        "tv": draw_tv,
        "amplifier": draw_amplifier,
        "default": draw_default
    }
    
    for name, func in icons.items():
        # Standard / Inactive
        create_bmp(80, 80, lambda w, h, p: func(w, h, p, active=False), f"{target_dir}/{name}.png")
        # Active
        create_bmp(80, 80, lambda w, h, p: func(w, h, p, active=True), f"{target_dir}/{name}_active.png")

if __name__ == "__main__":
    main()
