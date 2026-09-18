#!/usr/bin/env python3
"""Ferro Bocce — neon court-roll arcade for ElbowOS."""
import argparse, math, os, random, subprocess, sys

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

W, H = 1080, 1920
FPS = 30
TITLE = "FERRO BOCCE"
HANDLE = "x.com/ElbowOS"
PAL = {
    "bg": (18, 10, 8),
    "soil": (42, 18, 12),
    "lane": (78, 28, 16),
    "plank": (128, 52, 22),
    "gold": (255, 186, 64),
    "amber": (255, 220, 120),
    "lime": (168, 255, 72),
    "mint": (72, 255, 176),
    "coral": (255, 86, 64),
    "rose": (255, 140, 110),
    "white": (255, 246, 230),
    "ink": (12, 6, 4),
    "dim": (110, 70, 48),
}

JACK_COLS = [(255, 86, 64), (168, 255, 72), (72, 220, 255), (255, 186, 64), (255, 110, 200)]


class Ball:
    def __init__(self, x, y, r, col, mass=1.0, jack=False):
        self.x, self.y, self.r, self.col = x, y, r, col
        self.vx = self.vy = 0.0
        self.mass = mass
        self.jack = jack
        self.live = True
        self.glow = 0


class Game:
    def __init__(self, auto=False):
        self.auto = auto
        self.t = self.score = self.combo = self.pockets = 0
        self.flash = self.cool = self.charge = 0
        self.aim = -math.pi / 2
        self.charging = False
        self.sparks = []
        self.dust = [(random.randrange(W), random.randrange(H), random.randint(1, 3)) for _ in range(55)]
        self.bumpers = []
        self._court()
        self._reset_throw()

    def _court(self):
        self.left, self.right = 130, W - 130
        self.top, self.bot = 280, 1680
        self.wells = [
            (self.left + 40, 420, 46),
            (self.right - 40, 420, 46),
            (self.left + 40, 780, 40),
            (self.right - 40, 780, 40),
            (W * 0.5, 340, 52),
        ]
        self.bumpers = [
            [W * 0.5 + 160, 980, 34, 1.4],
            [W * 0.5 - 180, 1120, 30, -1.1],
            [W * 0.5 + 40, 620, 28, 0.9],
        ]

    def _reset_throw(self):
        self.ball = Ball(W * 0.5, self.bot - 70, 38, PAL["amber"], 1.2, False)
        self.flying = False
        self.charge = 0
        self.charging = False
        if not getattr(self, "jacks", None) or sum(1 for j in self.jacks if j.live) < 3:
            self.jacks = []
            for i in range(5):
                x = random.randint(self.left + 80, self.right - 80)
                y = random.randint(self.top + 80, 1200)
                self.jacks.append(Ball(x, y, 26, JACK_COLS[i], 0.7, True))

    def launch(self):
        if self.flying or self.cool:
            return
        pwr = 16 + self.charge * 0.55
        self.ball.vx = math.cos(self.aim) * pwr
        self.ball.vy = math.sin(self.aim) * pwr
        self.flying = True
        self.charging = False
        self.charge = 0
        self.cool = 6

    def _bounce_walls(self, b):
        if b.x - b.r < self.left:
            b.x = self.left + b.r
            b.vx = abs(b.vx) * 0.82
        if b.x + b.r > self.right:
            b.x = self.right - b.r
            b.vx = -abs(b.vx) * 0.82
        if b.y - b.r < self.top:
            b.y = self.top + b.r
            b.vy = abs(b.vy) * 0.7
        if b.y + b.r > self.bot:
            b.y = self.bot - b.r
            b.vy = -abs(b.vy) * 0.45
            b.vx *= 0.85

    def _collide(self, a, b):
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy) or 0.01
        if d >= a.r + b.r:
            return
        nx, ny = dx / d, dy / d
        overlap = a.r + b.r - d
        inv = 1 / a.mass + 1 / b.mass
        a.x -= nx * overlap * (1 / a.mass) / inv
        a.y -= ny * overlap * (1 / a.mass) / inv
        b.x += nx * overlap * (1 / b.mass) / inv
        b.y += ny * overlap * (1 / b.mass) / inv
        rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
        if rv > 0:
            return
        imp = -(1.35) * rv / inv
        a.vx -= imp / a.mass * nx
        a.vy -= imp / a.mass * ny
        b.vx += imp / b.mass * nx
        b.vy += imp / b.mass * ny
        b.glow = 8
        for _ in range(8):
            ang = random.random() * 6.28
            self.sparks.append([b.x, b.y, math.cos(ang) * 6, math.sin(ang) * 6, 12, b.col])

    def _pocket(self, j):
        for wx, wy, wr in self.wells:
            if math.hypot(j.x - wx, j.y - wy) < wr - 6:
                j.live = False
                pts = 40 + self.combo * 12
                self.score += pts
                self.combo += 1
                self.pockets += 1
                self.flash = 8
                for _ in range(18):
                    ang = random.random() * 6.28
                    self.sparks.append([wx, wy, math.cos(ang) * 9, math.sin(ang) * 9, 16, PAL["lime"]])
                return True
        return False

    def autoplay(self):
        live = [j for j in self.jacks if j.live]
        if not live:
            return
        tgt = min(live, key=lambda j: math.hypot(j.x - self.ball.x, j.y - self.ball.y))
        want = math.atan2(tgt.y - self.ball.y, tgt.x - self.ball.x)
        diff = (want - self.aim + math.pi) % (6.2832) - math.pi
        self.aim += max(-0.08, min(0.08, diff * 0.25))
        if not self.flying:
            dist = math.hypot(tgt.x - self.ball.x, tgt.y - self.ball.y)
            need = min(42, 18 + dist * 0.028)
            if self.charge < need:
                self.charging = True
            else:
                self.launch()

    def step(self, keys=None):
        self.t += 1
        self.cool = max(0, self.cool - 1)
        self.flash = max(0, self.flash - 1)
        for b in self.bumpers:
            b[0] += math.sin(self.t * 0.04 + b[3]) * 1.6
            b[0] = max(self.left + 50, min(self.right - 50, b[0]))
        if self.auto:
            self.autoplay()
        elif keys is not None:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.aim -= 0.045
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.aim += 0.045
            hold = keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]
            if hold and not self.flying:
                self.charging = True
            elif self.charging and not self.flying:
                self.launch()
        if self.charging and not self.flying:
            self.charge = min(48, self.charge + 1.4)
        balls = [self.ball] + [j for j in self.jacks if j.live]
        if self.flying:
            for b in balls:
                b.vy += 0.18
                b.vx *= 0.992
                b.vy *= 0.992
                b.x += b.vx
                b.y += b.vy
                b.glow = max(0, b.glow - 1)
                self._bounce_walls(b)
                for bm in self.bumpers:
                    dx, dy = b.x - bm[0], b.y - bm[1]
                    d = math.hypot(dx, dy) or 1
                    if d < b.r + bm[2]:
                        nx, ny = dx / d, dy / d
                        b.x = bm[0] + nx * (b.r + bm[2])
                        b.y = bm[1] + ny * (b.r + bm[2])
                        dot = b.vx * nx + b.vy * ny
                        b.vx = (b.vx - 2.1 * dot * nx) * 0.95
                        b.vy = (b.vy - 2.1 * dot * ny) * 0.95
            for j in self.jacks:
                if j.live:
                    self._collide(self.ball, j)
                    self._pocket(j)
            for i, a in enumerate(self.jacks):
                if not a.live:
                    continue
                for b in self.jacks[i + 1:]:
                    if b.live:
                        self._collide(a, b)
            spd = math.hypot(self.ball.vx, self.ball.vy)
            if spd < 0.55 and self.t % 8 == 0:
                self._reset_throw()
                self.combo = max(0, self.combo - 1)
        live = []
        for s in self.sparks:
            s[0] += s[2]
            s[1] += s[3]
            s[4] -= 1
            if s[4] > 0:
                live.append(s)
        self.sparks = live
        if sum(1 for j in self.jacks if j.live) == 0:
            self.score += 120
            self._reset_throw()

    def draw(self, surf, font, small, mid):
        surf.fill(PAL["bg"])
        for y in range(0, H, 10):
            k = y / H
            col = (int(18 + 40 * k), int(10 + 8 * k), int(8 + 4 * (1 - k)))
            pygame.draw.rect(surf, col, (0, y, W, 10))
        for x, y, r in self.dust:
            yy = (y + int(self.t * 0.4)) % H
            pygame.draw.circle(surf, (90, 50, 28), (x, yy), r)
        pygame.draw.rect(surf, PAL["lane"], (self.left - 18, self.top - 18,
                                             self.right - self.left + 36, self.bot - self.top + 36),
                         border_radius=36)
        pygame.draw.rect(surf, PAL["soil"], (self.left, self.top,
                                            self.right - self.left, self.bot - self.top),
                         border_radius=28)
        pygame.draw.rect(surf, PAL["gold"], (self.left, self.top,
                                            self.right - self.left, self.bot - self.top), 4,
                         border_radius=28)
        for i in range(8):
            yy = self.top + 40 + i * 160
            pygame.draw.line(surf, PAL["plank"], (self.left + 12, yy), (self.right - 12, yy), 2)
        for wx, wy, wr in self.wells:
            pygame.draw.circle(surf, PAL["ink"], (int(wx), int(wy)), wr)
            pygame.draw.circle(surf, PAL["lime"], (int(wx), int(wy)), wr, 3)
            pygame.draw.circle(surf, PAL["mint"], (int(wx), int(wy)), 8)
        for bm in self.bumpers:
            pygame.draw.circle(surf, PAL["coral"], (int(bm[0]), int(bm[1])), int(bm[2]))
            pygame.draw.circle(surf, PAL["white"], (int(bm[0]), int(bm[1])), int(bm[2]), 3)
            pygame.draw.circle(surf, PAL["amber"], (int(bm[0]), int(bm[1])), 8)
        for j in self.jacks:
            if not j.live:
                continue
            pygame.draw.circle(surf, j.col, (int(j.x), int(j.y)), j.r + (4 if j.glow else 0))
            pygame.draw.circle(surf, PAL["white"], (int(j.x), int(j.y)), j.r, 3)
            pygame.draw.circle(surf, PAL["ink"], (int(j.x - 6), int(j.y - 6)), 5)
        b = self.ball
        pygame.draw.circle(surf, PAL["gold"], (int(b.x), int(b.y)), b.r + 6, 2)
        pygame.draw.circle(surf, b.col, (int(b.x), int(b.y)), b.r)
        pygame.draw.circle(surf, PAL["white"], (int(b.x - 10), int(b.y - 12)), 8)
        if not self.flying:
            ex = b.x + math.cos(self.aim) * (90 + self.charge * 3)
            ey = b.y + math.sin(self.aim) * (90 + self.charge * 3)
            pygame.draw.line(surf, PAL["lime"], (b.x, b.y), (ex, ey), 5)
            pygame.draw.circle(surf, PAL["lime"], (int(ex), int(ey)), 8)
            if self.charge:
                bar = pygame.Rect(b.x - 70, b.y + 52, int(140 * (self.charge / 48)), 14)
                pygame.draw.rect(surf, PAL["coral"], bar, border_radius=6)
        for s in self.sparks:
            pygame.draw.circle(surf, s[5], (int(s[0]), int(s[1])), max(2, s[4] // 3))
        if self.flash:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((168, 255, 72, 16 * self.flash))
            surf.blit(veil, (0, 0))
        banner = pygame.Surface((W, 150), pygame.SRCALPHA)
        banner.fill((18, 8, 4, 190))
        surf.blit(banner, (0, 0))
        surf.blit(font.render(TITLE, True, PAL["gold"]), (40, 18))
        surf.blit(small.render(HANDLE, True, PAL["rose"]), (40, 88))
        sc = font.render(f"{self.score:05d}", True, PAL["white"])
        surf.blit(sc, (W - 48 - sc.get_width(), 18))
        meta = small.render(f"COMBO {self.combo}   WELLS {self.pockets}", True, PAL["lime"])
        surf.blit(meta, (W - 48 - meta.get_width(), 90))
        foot = small.render("A / D aim   HOLD SPACE to roll", True, PAL["dim"])
        surf.blit(foot, foot.get_rect(center=(W * 0.5, H - 70)))


def record(path):
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.font.init()
    surf = pygame.Surface((W, H))
    font = pygame.font.SysFont("DejaVu Sans", 58, bold=True)
    mid = pygame.font.SysFont("DejaVu Sans", 48, bold=True)
    small = pygame.font.SysFont("DejaVu Sans", 34, bold=True)
    g = Game(auto=True)
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "20", "-preset", "fast", "-movflags", "+faststart", path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    frames = FPS * 15
    try:
        for _ in range(frames):
            g.step()
            g.draw(surf, font, small, mid)
            proc.stdin.write(pygame.image.tostring(surf, "RGB"))
        proc.stdin.close()
        err = proc.stderr.read()
        rc = proc.wait(timeout=60)
    except Exception:
        proc.kill()
        raise
    if rc != 0:
        raise RuntimeError(err.decode("utf-8", "ignore")[-800:])
    print("wrote", path)


def play():
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("DejaVu Sans", 58, bold=True)
    mid = pygame.font.SysFont("DejaVu Sans", 48, bold=True)
    small = pygame.font.SysFont("DejaVu Sans", 34, bold=True)
    g = Game(auto=False)
    run = True
    while run:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                run = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                run = False
        g.step(pygame.key.get_pressed())
        g.draw(screen, font, small, mid)
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--record", action="store_true")
    p.add_argument("--play", action="store_true")
    p.add_argument("--out", default="/home/workdir/artifacts/FERRO_BOCCE_ElbowOS.mp4")
    a = p.parse_args()
    if a.record or not a.play:
        record(a.out)
        if a.play:
            play()
    else:
        play()


if __name__ == "__main__":
    main()
