## /\nd|0r-style machine readout - Tildagon badge app
## Fans driven by live IMU + PMIC sensors. Timer arc = countdown ring.
## Angles: clock degrees, 0 = 12 o'clock, clockwise.

import math
import app
from app_components import clear_background
from events.input import Buttons, BUTTON_TYPES

try:
    import imu as _imu
except ImportError:
    _imu = None

try:
    import power as _power
except ImportError:
    _power = None

R = 120.0
PERIOD       = 5.0   # timer countdown loop
SCENE_PERIOD = 5.0   # seconds per scene before switching

DEEP  = (0.051, 0.157, 0.275)
MID   = (0.118, 0.302, 0.451)
CYAN  = (0.349, 0.596, 0.718)
CREAM = (0.710, 0.796, 0.761)
BG_CTR= (0.133, 0.290, 0.420)
BG_RIM= (0.071, 0.192, 0.314)
DKNAVY= (0.047, 0.110, 0.188)   # darker than the base field (FAN5)
RED    = (0.85,  0.18,  0.12)
CRIMSON= (0.45,  0.05,  0.05)
CORAL  = (0.80,  0.48,  0.38)

# ---------------------------------------------------------------- geometry
def _pt(a_deg, r):
    t = math.radians(a_deg)
    return (r * math.sin(t), -r * math.cos(t))

def _arc_pts(a0, a1, r, step=4.0):
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [_pt(a0 + (a1 - a0) * i / n, r) for i in range(n + 1)]

def _fill_poly(ctx, pts, col, alpha=1.0):
    if alpha <= 0.001 or len(pts) < 3:
        return
    ctx.rgba(col[0], col[1], col[2], alpha).begin_path()
    ctx.move_to(pts[0][0], pts[0][1])
    for x, y in pts[1:]:
        ctx.line_to(x, y)
    ctx.close_path().fill()

def annular(ctx, a0, a1, r_in, r_out, col, alpha=1.0):
    pts = _arc_pts(a0, a1, r_out) + list(reversed(_arc_pts(a0, a1, r_in)))
    _fill_poly(ctx, pts, col, alpha)

def toothed_sector(ctx, a0, a1, r_in, r_out, col, amp=6.0, step=5.0, alpha=1.0):
    pts = _arc_pts(a0, a1, r_out)
    n = max(2, int((a1 - a0) / step))
    for i in range(n + 1):
        a = a1 - (a1 - a0) * i / n
        r = r_in if (i % 2 == 0) else (r_in + amp)
        pts.append(_pt(a, r))
    _fill_poly(ctx, pts, col, alpha)

def pin(ctx, a, r0, r1, w, col, tick=0.0, tick_at=None, tick_side=-1, alpha=1.0):
    if alpha <= 0.001:
        return
    x0, y0 = _pt(a, r0); x1, y1 = _pt(a, r1)
    ctx.rgba(col[0], col[1], col[2], alpha)
    ctx.line_width = w
    ctx.begin_path(); ctx.move_to(x0, y0); ctx.line_to(x1, y1); ctx.stroke()
    if tick > 0 and tick_at is not None:
        rt = r0 + (r1 - r0) * tick_at
        bx, by = _pt(a, rt)
        t = math.radians(a)
        lx, ly = (-math.cos(t), -math.sin(t))
        if tick_side > 0:
            lx, ly = -lx, -ly
        ctx.line_width = w * 0.85
        ctx.begin_path(); ctx.move_to(bx, by); ctx.line_to(bx + lx * tick, by + ly * tick); ctx.stroke()

def bracket(ctx, col, w=5.0, half=40.0, top=-6.0, drop=18.0, hook=11.0, notch=4.0):
    yb = top; yd = yb + drop; L = -half; Rr = half
    ctx.rgba(col[0], col[1], col[2], 1.0); ctx.line_width = w
    ctx.begin_path(); ctx.move_to(L + hook, yd); ctx.line_to(L, yd); ctx.line_to(L, yb)
    ctx.line_to(-notch, yb); ctx.line_to(-notch, yb - 6); ctx.stroke()
    ctx.begin_path(); ctx.move_to(notch, yb - 6); ctx.line_to(notch, yb); ctx.line_to(Rr, yb)
    ctx.line_to(Rr, yd); ctx.line_to(Rr - hook, yd); ctx.stroke()

def disc_circle(ctx, r, col, alpha=1.0):
    ctx.rgba(col[0], col[1], col[2], alpha)
    ctx.begin_path(); ctx.arc(0, 0, r, 0, 2 * math.pi, True); ctx.fill()

def _stroke_path(ctx, pts, col, lw=1.5, close=True):
    ctx.rgba(col[0], col[1], col[2], 1.0)
    ctx.line_width = lw
    ctx.begin_path()
    ctx.move_to(pts[0][0], pts[0][1])
    for x, y in pts[1:]:
        ctx.line_to(x, y)
    if close:
        ctx.close_path()
    ctx.stroke()

# ---------------------------------------------------------------- components
# FAN: (key, center clock, tone, tooth amp). darker first so lighter draws on top.
FANS = [("f5", 175, DKNAVY, 6),                 # behind, darker than background
        ("f1", 200, MID, 6), ("f4", 22, MID, 6), ("f2", 158, CYAN, 6), ("f3", 358, CYAN, 6)]
# pins: (clock_angle, r0, r1, side) — tick params come from state
PINS = [(346, 14, 108, -1), (35, 40, 108, -1), (127, 40, 104, -1)]

_CHARGE_TICK = {
    "Not Charging": (0,  0.0),
    "Pre-Charging": (12, 0.33),
    "Fast Charging": (12, 0.66),
    "Terminated":   (12, 1.0),
}

def fan(ctx, c, width, tone, amp):
    if width > 1:
        toothed_sector(ctx, c - width / 2, c + width / 2, 44, 116, tone, amp=amp, step=5)

def timer_arc(ctx, span):
    if span <= 1:
        return
    if span >= 359.5:
        annular(ctx, 0, 360, 58, 98, CREAM)
    else:
        annular(ctx, 90 - span, 90, 58, 98, CREAM)

# ---------------------------------------------------------------- sensors
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _read_sensors(t=0.0):
    if _imu is not None:
        ax, ay, az = _imu.acc_read()
        gx, gy, gz = _imu.gyro_read()
        mag  = math.sqrt(ax*ax + ay*ay + az*az)
        gmag = math.sqrt(gx*gx + gy*gy + gz*gz)
        temp = _imu.temperature_read()
    else:
        ax = ay = az = gx = gy = gz = 0.0
        mag = 9.8; gmag = 0.0
        # animate heat when no IMU so the scene is visible on desktop
        temp = 20.0 + 25.0 * (0.5 + 0.4 * math.sin(2 * math.pi * t / SCENE_PERIOD))

    if _power is not None:
        level  = _power.BatteryLevel()
        cstate = _power.BatteryChargeState()
    else:
        level  = 0.8
        cstate = "Not Charging"

    p2_tk, p2_ta = _CHARGE_TICK.get(cstate, (0, 0.0))

    return {
        "f1": _clamp(abs(ax) * 4.0, 0, 80),          # lateral tilt
        "f2": _clamp(abs(ay) * 4.0, 0, 80),          # fore/aft tilt
        "f3": _clamp((mag - 9.8) * 4.5, 0, 80),      # shake energy
        "f4": _clamp(gmag * 23.0, 0, 80),             # total rotation rate
        "f5": _clamp(abs(gz) * 40.0, 0, 80),          # yaw / spin
        "p1_ta": level,                                # battery level → pin 1 tick
        "p2_tk": p2_tk,                                # charge state → pin 2 tick len
        "p2_ta": p2_ta,                                # charge state → pin 2 tick pos
        "p3_ta": _clamp((temp - 20.0) / 30.0, 0, 1), # temperature → pin 3 tick
        "heat":  _clamp((temp - 20.0) / 30.0, 0, 1), # thruster heat level
    }

def render(ctx, s):
    disc_circle(ctx, R, BG_RIM)
    annular(ctx, 0, 360, R * 0.86, R, BG_RIM)      # vignette rim
    for key, c, tone, amp in FANS:                  # fans first (CYAN over MID)
        fan(ctx, c, s[key], tone, amp)
    timer_arc(ctx, s["timer"])                      # G0 countdown ON TOP of fans
    pin_ticks = [(12, s["p1_ta"]), (s["p2_tk"], s["p2_ta"]), (11, s["p3_ta"])]
    for (a, r0, r1, sd), (tk, ta) in zip(PINS, pin_ticks):
        pin(ctx, a, r0, r1, 5.5, CYAN, tk, ta, sd)
    bracket(ctx, CYAN)
    for dx, rr in ((-11, 2.6), (11, 2.1)):          # eyes
        ctx.rgb(DEEP[0], DEEP[1], DEEP[2]).begin_path()
        ctx.arc(dx, 7, rr, 0, 2 * math.pi, True); ctx.fill()

# ---------------------------------------------------------------- thruster scene
def render_thruster(ctx, s):
    heat  = s["heat"]
    n_red = int(heat * 7)
    alarm = heat > 0.65

    _fill_poly(ctx, [(-120,-120),(120,-120),(120,120),(-120,120)], BG_RIM)

    # port nacelle heat fill — bottom third of left pod, grows with heat
    if heat > 0.02:
        _fill_poly(ctx, [(-80,15),(-55,15),(-55,45),(-80,45)], CRIMSON, min(1.0, heat * 1.4))

    # port nacelle
    _stroke_path(ctx, [(-80,-75),(-55,-75),(-55,45),(-80,45)], CYAN)
    _stroke_path(ctx, [(-72,-82),(-66,-82),(-66,-75),(-72,-75)], CYAN)   # antenna bump
    _stroke_path(ctx, [(-77,-68),(-58,-68),(-58,-56),(-77,-56)], CYAN)   # inner sensor rect

    # starboard nacelle
    _stroke_path(ctx, [(55,-75),(80,-75),(80,45),(55,45)], CYAN)
    _stroke_path(ctx, [(66,-82),(72,-82),(72,-75),(66,-75)], CYAN)        # antenna bump
    _stroke_path(ctx, [(58,-68),(77,-68),(77,-56),(58,-56)], CYAN)        # inner sensor rect

    # wings
    _stroke_path(ctx, [(-55,-18),(-55,2),(-24,-8),(-24,-22)], CYAN)
    _stroke_path(ctx, [(24,-22),(24,-8),(55,2),(55,-18)], CYAN)

    # central fuselage
    _stroke_path(ctx, [(-24,-83),(24,-83),(24,-22),(22,24),(14,70),(-14,70),(-22,24),(-24,-22)], CYAN)
    _stroke_path(ctx, [(-10,-76),(10,-76),(10,-62),(-10,-62)], CYAN)      # top compartment
    _stroke_path(ctx, [(-8,-40),(8,-40),(8,-28),(-8,-28)], CYAN)          # mid detail
    ctx.rgba(CYAN[0], CYAN[1], CYAN[2], 1.0)
    ctx.line_width = 1.5
    ctx.begin_path(); ctx.arc(0, 8, 13, 0, 2 * math.pi, True); ctx.stroke()

    # bar meter (two columns, aligned with port nacelle)
    BX = -108; BW = 7; BH = 6; BG = 2; BY0 = 5
    for i in range(7):
        by  = BY0 + i * (BH + BG)
        col = RED if i < n_red else CREAM
        _fill_poly(ctx, [(BX,by),(BX+BW,by),(BX+BW,by+BH),(BX,by+BH)], col)
        _fill_poly(ctx, [(BX+BW+2,by),(BX+BW*2+2,by),(BX+BW*2+2,by+BH),(BX+BW+2,by+BH)], col)

    # callout lines: bar group → port nacelle (small open square at ship end)
    ctx.rgba(CREAM[0], CREAM[1], CREAM[2], 1.0); ctx.line_width = 1.0
    for cy in (22, 42):
        ctx.begin_path(); ctx.move_to(-89, cy); ctx.line_to(-80, cy); ctx.stroke()
        _stroke_path(ctx, [(-83,cy-2),(-80,cy-2),(-80,cy+2),(-83,cy+2)], CREAM, 1.0)

    # callout lines: starboard nacelle → right side
    for cy in (22, 42):
        ctx.rgba(CREAM[0], CREAM[1], CREAM[2], 1.0); ctx.line_width = 1.0
        ctx.begin_path(); ctx.move_to(80, cy); ctx.line_to(95, cy); ctx.stroke()
        _stroke_path(ctx, [(80,cy-2),(83,cy-2),(83,cy+2),(80,cy+2)], CREAM, 1.0)

    # top nacelle callout lines
    ctx.rgba(CREAM[0], CREAM[1], CREAM[2], 1.0); ctx.line_width = 1.0
    for nx, lx in ((-68, -112), (68, 112)):
        ctx.begin_path(); ctx.move_to(nx, -78); ctx.line_to(lx, -65); ctx.stroke()

    # fuselage centre callout
    ctx.begin_path(); ctx.move_to(8, -34); ctx.line_to(95, -34); ctx.stroke()

    # red label stubs (left side, suggest alarm text)
    ctx.rgba(RED[0], RED[1], RED[2], 1.0); ctx.line_width = 1.0
    for ly in (8, 26, 44):
        ctx.begin_path(); ctx.move_to(-118, ly); ctx.line_to(-111, ly); ctx.stroke()

    # alarm box (appears above heat threshold)
    if alarm:
        _stroke_path(ctx, [(-108,62),(-66,62),(-66,80),(-108,80)], RED, 1.5)
        _fill_poly(ctx, [(-104,66),(-70,66),(-70,76),(-104,76)], RED, 0.5)

# ---------------------------------------------------------------- countermeasures scene
_RING_COL = (0.04, 0.12, 0.20)

def render_countermeasures(ctx, u):
    charge     = u
    charge_end = 180.0 + charge * 180.0           # sweeps 180°→360° as charge 0→1
    hud_col    = CORAL if charge > 0.98 else CREAM # brackets/number go coral at full charge

    disc_circle(ctx, R, BG_RIM)

    # left half — background layers, back to front
    annular(ctx, 180, 330, 0, R * 0.98, CYAN)      # teal base
    annular(ctx, 330, 360, 0, R * 0.98, DKNAVY)    # dark cap at top of left half
    if charge > 0.001:
        annular(ctx, 180, charge_end, 0, R * 0.98, CORAL)  # charged sweep

    # concentric ring outlines (left half arc only)
    for r_ring in (38, 62, 88):
        pts = _arc_pts(180, 360, r_ring)
        ctx.rgba(_RING_COL[0], _RING_COL[1], _RING_COL[2], 1.0)
        ctx.line_width = 1.8
        ctx.begin_path()
        ctx.move_to(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            ctx.line_to(x, y)
        ctx.stroke()

    # centre white disc
    disc_circle(ctx, 26, CREAM)

    # vertical dividing line
    ctx.rgba(_RING_COL[0], _RING_COL[1], _RING_COL[2], 0.8)
    ctx.line_width = 1.5
    ctx.begin_path(); ctx.move_to(0, -R); ctx.line_to(0, R); ctx.stroke()

    # right half — corner bracket markers
    bxL = 12; bxM = 74; bxN = 88; byT = -66; byM = -22
    _stroke_path(ctx, [(bxL,byT),(bxM,byT),(bxM,byM),(bxN,byM)], hud_col, lw=3.5, close=False)
    _stroke_path(ctx, [(bxN,-byM),(bxM,-byM),(bxM,-byT),(bxL,-byT)], hud_col, lw=3.5, close=False)

    # alien-text placeholder (three short bars)
    ctx.rgba(hud_col[0], hud_col[1], hud_col[2], 0.85)
    ctx.line_width = 2.0
    for i, w in enumerate((26, 46, 20)):
        y = -8 + i * 9
        ctx.begin_path(); ctx.move_to(28, y); ctx.line_to(28 + w, y); ctx.stroke()

    # charge number
    ctx.rgba(hud_col[0], hud_col[1], hud_col[2], 1.0)
    ctx.font_size = 16
    ctx.move_to(28, 22)
    ctx.text(str(int(charge * 1000)))

# ---------------------------------------------------------------- tractor beam scene
def render_tractor_beam(ctx, u):
    _HOT  = (1.00, 0.70, 0.45)  # bright orange — "gets stronger"
    _FAIL = (0.75, 0.22, 0.12)  # dark red — "down a colour"
    N = 22
    bx0, bx1 = -76, 28

    _fill_poly(ctx, [(-120,-120),(120,-120),(120,120),(-120,120)], BG_RIM)

    # Emitter: small horizontal oval at far left
    oval = [(-90 + 14*math.cos(2*math.pi*i/20), 5*math.sin(2*math.pi*i/20)) for i in range(20)]
    _stroke_path(ctx, oval, CREAM, lw=1.5)

    # Phase control — 6 phases over u=[0,1]
    # 0.00–0.12  dark (no beam)
    # 0.12–0.42  build: lines appear right→left (emitter outward toward oval)
    # 0.42–0.58  lock: full beam, corner brackets appear on ship
    # 0.58–0.75  stronger: HOT colour front sweeps left→right
    # 0.75–0.88  reverse: FAIL colour front sweeps right→left
    # 0.88–1.00  fail: beam retracts left→right (pulling back to emitter)
    i_from   = N   # draw lines i_from..N-1 (rightmost first during build)
    i_to     = N
    hot_idx  = 0   # lines [0, hot_idx) are HOT
    fail_idx = N   # lines [fail_idx, N) are FAIL
    lock_col = None

    if u < 0.12:
        pass

    elif u < 0.42:
        prog   = (u - 0.12) / 0.30
        i_from = max(0, N - int(prog * N + 1))
        i_to   = N

    elif u < 0.58:
        i_from   = 0;  i_to = N
        lock_col = CORAL

    elif u < 0.75:
        prog     = (u - 0.58) / 0.17
        i_from   = 0;  i_to = N
        hot_idx  = int(prog * N)
        lock_col = CORAL

    elif u < 0.88:
        prog     = (u - 0.75) / 0.13
        i_from   = 0;  i_to = N
        hot_idx  = N
        fail_idx = int((1.0 - prog) * N)
        lock_col = _FAIL

    else:
        prog     = (u - 0.88) / 0.12
        i_from   = min(N, int(prog * N))
        i_to     = N
        fail_idx = 0

    # Draw beam lines (width is fixed by position, never pulsed)
    for i in range(i_from, i_to):
        frac = i / (N - 1)
        x    = bx0 + frac * (bx1 - bx0)
        h    = 68.0 * (1.0 - frac) ** 0.65
        if h < 0.5:
            continue
        col  = _FAIL if i >= fail_idx else (_HOT if i < hot_idx else CORAL)
        a    = 1.0 - frac * 0.4
        lw   = max(0.9, 3.0 - frac * 2.1)
        ctx.rgba(col[0], col[1], col[2], a)
        ctx.line_width = lw
        ctx.begin_path()
        ctx.move_to(x, -h * 0.5); ctx.line_to(x, h * 0.5)
        ctx.stroke()

    # Corner brackets around ship — appear when locked (phases 2–4)
    if lock_col is not None:
        ctx.rgba(lock_col[0], lock_col[1], lock_col[2], 1.0)
        ctx.line_width = 1.5
        for sx, sy, dx, dy in ((40,-14,1,1),(110,-14,-1,1),(40,14,1,-1),(110,14,-1,-1)):
            ctx.begin_path()
            ctx.move_to(sx + dx*10, sy); ctx.line_to(sx, sy); ctx.line_to(sx, sy + dy*8)
            ctx.stroke()

    # Target ship wireframe (CYAN, always visible)
    _stroke_path(ctx, [(42,-14),(42,14),(50,4),(50,-4)], CYAN)
    ctx.rgba(CYAN[0],CYAN[1],CYAN[2],1.0); ctx.line_width = 1.5
    ctx.begin_path(); ctx.move_to(50,-3); ctx.line_to(100,-3); ctx.stroke()
    ctx.begin_path(); ctx.move_to(50, 3); ctx.line_to(100, 3); ctx.stroke()
    _stroke_path(ctx, [(65,-3),(65,-11),(81,-11),(81,-3)], CYAN, lw=1.5, close=False)
    _stroke_path(ctx, [(65, 3),(65, 11),(81, 11),(81, 3)], CYAN, lw=1.5, close=False)
    ctx.rgba(CYAN[0],CYAN[1],CYAN[2],1.0); ctx.line_width = 1.5
    for bx in (70, 76):
        ctx.begin_path(); ctx.move_to(bx,-11); ctx.line_to(bx,-3); ctx.stroke()
        ctx.begin_path(); ctx.move_to(bx,  3); ctx.line_to(bx,11); ctx.stroke()
    _stroke_path(ctx, [(100,-7),(108,-3),(108,3),(100,7)], CYAN)

    # Bottom readout: three groups, numbers track beam build progress
    vis = min(1.0, max(0.0, (u - 0.12) / 0.30))
    ctx.rgba(CYAN[0], CYAN[1], CYAN[2], 1.0); ctx.line_width = 1.5
    for cx, val in zip((-72, 0, 62), (int(vis*96), int(vis*80), int(vis*56+26))):
        by = 60
        ctx.begin_path(); ctx.move_to(cx-8, by);    ctx.line_to(cx+6, by);    ctx.stroke()
        ctx.begin_path(); ctx.move_to(cx-6, by+6);  ctx.line_to(cx+4, by+6);  ctx.stroke()
        ctx.begin_path(); ctx.move_to(cx-8, by+12); ctx.line_to(cx,   by+12); ctx.stroke()
        ctx.font_size = 12
        ctx.move_to(cx - 6, 82)
        ctx.text(str(val))

# ---------------------------------------------------------------- app
# keys smoothed with EMA (continuous values); p2_tk/p2_ta are discrete, kept raw
_SMOOTH_INIT = {"f1": 20.0, "f2": 20.0, "f3": 10.0, "f4": 10.0, "f5": 10.0,
                "p1_ta": 0.8, "p3_ta": 0.5, "heat": 0.5}
_EMA = 0.85  # higher = smoother / slower

class ReadoutApp(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.t = 0.0
        self.paused = False
        self._smooth = dict(_SMOOTH_INIT)
        self._p2 = (0, 0.0)  # (tick_len, tick_at) for charge-state pin

    def update(self, delta):
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear(); self.minimise(); return
        if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear(); self.paused = not self.paused
        if not self.paused:
            self.t += (delta / 1000.0) if (delta and delta > 1) else (delta or 0.05)
            raw = _read_sensors(self.t)
            for k in self._smooth:
                self._smooth[k] = _EMA * self._smooth[k] + (1 - _EMA) * raw[k]
            self._p2 = (raw["p2_tk"], raw["p2_ta"])

    def draw(self, ctx):
        clear_background(ctx)
        ctx.save()
        u     = (self.t % SCENE_PERIOD) / SCENE_PERIOD
        scene = int(self.t / SCENE_PERIOD) % 4
        if scene == 0:
            s = {"timer": 360 * (1 - u)}
            s.update(self._smooth)
            s["p2_tk"], s["p2_ta"] = self._p2
            render(ctx, s)
        elif scene == 1:
            render_thruster(ctx, {"heat": self._smooth["heat"]})
        elif scene == 2:
            render_countermeasures(ctx, u)
        else:
            render_tractor_beam(ctx, u)
        ctx.restore()


__app_export__ = ReadoutApp