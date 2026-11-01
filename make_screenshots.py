"""Render each game screen headlessly and save PNG screenshots."""
import os
import random
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["APPDATA"] = tempfile.mkdtemp()  # don't touch the real leaderboard

import pygame  # noqa: E402

import bounce_box as bb  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "screenshots"
os.makedirs(out, exist_ok=True)
random.seed(7)

pygame.init()
screen = pygame.display.set_mode((bb.WIDTH, bb.HEIGHT))
g = bb.Game(screen)
g.board = [
    {"name": n, "score": s}
    for n, s in [("ZARA", 1840), ("MAX", 1420), ("SAM", 1130), ("LEO", 960), ("AVA", 720),
                 ("KAI", 610), ("MIA", 450), ("NOAH", 330)]
]


def shot(name, frames=0):
    for _ in range(frames):
        g.step()
    g.shake = 0
    g.render()
    pygame.image.save(g.canvas, os.path.join(out, name))
    print("saved", name)


# Menu
g.menu_buttons[0].hover = True
shot("1_menu.png", 40)
g.menu_buttons[0].hover = False

# Gameplay: simulate an auto-playing paddle for a while
g.reset()
g.state = "play"
g.use_mouse = False
for i in range(4000):
    g.paddle.x = g.ball.x - bb.Paddle.W / 2 + 20
    g.paddle.x = max(bb.ARENA.left + bb.WALL, min(bb.ARENA.right - bb.WALL - bb.Paddle.W, g.paddle.x))
    g.paddle.rect.x = int(g.paddle.x)
    g.step()
    if g.star and i > 3200:
        break
if not g.star:
    g.star = bb.Star()
# capture right after a paddle hit for juicy particles
for _ in range(400):
    g.paddle.x = g.ball.x - bb.Paddle.W / 2 + 20
    g.paddle.x = max(bb.ARENA.left + bb.WALL, min(bb.ARENA.right - bb.WALL - bb.Paddle.W, g.paddle.x))
    g.paddle.rect.x = int(g.paddle.x)
    before = g.hits
    g.step()
    if g.hits > before:
        break
shot("2_gameplay.png", 6)

# Pause
g.state = "pause"
shot("3_paused.png")

# New high score name entry
g.state = "enter_name"
g.lives = 0
g.name = "SHEHERYAR"
g.particles.clear()
g.popups.clear()
shot("4_new_highscore.png")

# Leaderboard (with the new score highlighted)
g.submit_name()
g.tick = 0
shot("5_leaderboard.png")

# Game over (no high score)
g.state = "gameover"
g.score = 120
shot("6_game_over.png")
pygame.quit()
