import pygame
import random
import math
from collections import deque
from Map_creator import create_map

pygame.init()

info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
FPS = 60
DEBUG = True  # remember to set DEBUG to False before final submission
PLAYER_SPEED = 3
PLAYER_SPRINT_SPEED = 5
PLAYER_MAX_STAMINA = 100
PLAYER_SPRINT_STAMINA_DRAIN = 25
PLAYER_STAMINA_REGEN_DELAY_MS = 1000
PLAYER_ATTACK_STAMINA_COST = 20
PLAYER_WALK_STAMINA_REGEN = 15
PLAYER_IDLE_STAMINA_REGEN = 30
PLAYER_MAX_HEALTH = 20
PLAYER_ATTACK_DAMAGE = 6
PLAYER_ATTACK_RANGE = 40
PLAYER_SWORD_SWING_DURATION_MS = 220
PLAYER_SWORD_SWING_ARC_DEGREES = 120
PLAYER_ATTACK_KNOCKBACK_SPEED = 12
KNOCKBACK_FRICTION = 0.82
PLAYER_ATTACK_COOLDOWN_MS = 400
SPIDER_MAX_HEALTH = 16
SPIDER_ATTACK_DAMAGE = 1
SPIDER_ATTACK_RANGE = 4
SPIDER_ATTACK_COOLDOWN_MS = 1000
DAMAGE_PARTICLE_COUNT = 8
DAMAGE_PARTICLE_LIFETIME = 0.35
AMOUNT_OF_SPIDERS = random.randint(5, 10)
MOBS = []
PARTICLES = []

SPIDER_IMAGE = pygame.image.load("Dungi/Spider.png")

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Dungi")

GAME_MAP = create_map((WIDTH, HEIGHT))

clock = pygame.time.Clock()
font = pygame.font.Font(None, 28)
attack_range_indicator = pygame.Surface(
    (PLAYER_ATTACK_RANGE * 2, PLAYER_ATTACK_RANGE * 2),
    pygame.SRCALPHA,
)
pygame.draw.circle(
    attack_range_indicator,
    (255, 220, 0, 45),
    (PLAYER_ATTACK_RANGE, PLAYER_ATTACK_RANGE),
    PLAYER_ATTACK_RANGE,
)
pygame.draw.circle(
    attack_range_indicator,
    (255, 220, 0, 160),
    (PLAYER_ATTACK_RANGE, PLAYER_ATTACK_RANGE),
    PLAYER_ATTACK_RANGE,
    2,
)

player_rect = pygame.Rect(WIDTH // 2, HEIGHT // 2, 24, 40)
PLAYER_IMAGE = pygame.image.load("Dungi/Player.png").convert_alpha()
PLAYER_IMAGE = pygame.transform.smoothscale(PLAYER_IMAGE, (player_rect.width, player_rect.height))
player_health = PLAYER_MAX_HEALTH
player_stamina = PLAYER_MAX_STAMINA
player_facing = pygame.Vector2(1, 0)
last_sword_swing = -PLAYER_SWORD_SWING_DURATION_MS
last_sword_swing_facing = pygame.Vector2(player_facing)
last_sprint_time = pygame.time.get_ticks()
last_player_attack = -PLAYER_ATTACK_COOLDOWN_MS


def spawn_damage_particles(position, color):
    for _ in range(DAMAGE_PARTICLE_COUNT):
        direction = pygame.Vector2(
            random.uniform(-1, 1),
            random.uniform(-1, 1),
        )
        if direction.length_squared() == 0:
            direction.x = 1
        direction.normalize_ip()
        PARTICLES.append({
            "position": pygame.Vector2(position),
            "velocity": direction * random.uniform(45, 120),
            "color": color,
            "lifetime": DAMAGE_PARTICLE_LIFETIME,
        })


def update_damage_particles(delta_seconds):
    for particle in PARTICLES:
        particle["position"] += particle["velocity"] * delta_seconds
        particle["lifetime"] -= delta_seconds
    PARTICLES[:] = [
        particle for particle in PARTICLES
        if particle["lifetime"] > 0
    ]


def draw_damage_particles():
    for particle in PARTICLES:
        progress = particle["lifetime"] / DAMAGE_PARTICLE_LIFETIME
        radius = max(1, round(4 * progress))
        pygame.draw.circle(
            screen,
            particle["color"],
            (round(particle["position"].x), round(particle["position"].y)),
            radius,
        )


def spawn_spider():
    for _ in range(1000):
        spider_rect = pygame.Rect(
            random.randint(
                GAME_MAP.playable_rect.left,
                GAME_MAP.playable_rect.right - 30,
            ),
            random.randint(
                GAME_MAP.playable_rect.top,
                GAME_MAP.playable_rect.bottom - 30,
            ),
            30,
            30,
        )
        if (
            GAME_MAP.is_walkable(spider_rect)
            and not spider_rect.colliderect(player_rect)
            and all(
                not spider_rect.colliderect(spider["rect"])
                for spider in MOBS
            )
        ):
            break
    else:
        raise RuntimeError(
            "Could not find an unoccupied cave floor tile for a spider"
        )

    MOBS.append({
        "rect": spider_rect,
        "image": SPIDER_IMAGE,
        "speed": random.randint(2, 4),
        "health": SPIDER_MAX_HEALTH,
        "next_attack_time": pygame.time.get_ticks() + SPIDER_ATTACK_COOLDOWN_MS,
        "knockback_velocity": pygame.Vector2(),
        "is_chasing": False,
        "last_known_player_position": None,
    })


for _ in range(AMOUNT_OF_SPIDERS):
    spawn_spider()



def movement(delta_seconds):
    global player_facing
    keys = pygame.key.get_pressed()
    horizontal_input = (
        int(keys[pygame.K_d] or keys[pygame.K_RIGHT])
        - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
    )
    vertical_input = (
        int(keys[pygame.K_s] or keys[pygame.K_DOWN])
        - int(keys[pygame.K_w] or keys[pygame.K_UP])
    )
    is_moving = horizontal_input != 0 or vertical_input != 0
    if is_moving:
        player_facing = pygame.Vector2(horizontal_input, vertical_input).normalize()
    is_sprinting = (
        is_moving
        and (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        and player_stamina > PLAYER_SPRINT_STAMINA_DRAIN * delta_seconds
    )
    speed = PLAYER_SPRINT_SPEED if is_sprinting else PLAYER_SPEED
    horizontal = (
        horizontal_input * speed
    )
    vertical = (
        vertical_input * speed
    )

    move_without_collision(
        player_rect,
        horizontal,
        vertical,
        [spider["rect"] for spider in MOBS] + GAME_MAP.wall_rects,
    )
        
    if keys[pygame.K_ESCAPE]:
        pygame.quit()
        exit()

    return is_moving, is_sprinting


def update_stamina(delta_seconds, is_moving, is_sprinting, now):
    global player_stamina, last_sprint_time
    keys = pygame.key.get_pressed()
    shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

    if is_sprinting:
        last_sprint_time = now
        player_stamina = max(
            0,
            player_stamina - PLAYER_SPRINT_STAMINA_DRAIN * delta_seconds,
        )
    elif (
        not shift_held
        and now - last_sprint_time >= PLAYER_STAMINA_REGEN_DELAY_MS
    ):
        regeneration = (
            PLAYER_WALK_STAMINA_REGEN
            if is_moving
            else PLAYER_IDLE_STAMINA_REGEN
        )
        player_stamina = min(
            PLAYER_MAX_STAMINA,
            player_stamina + regeneration * delta_seconds,
        )


def move_without_collision(rect, horizontal, vertical, blockers):
    rect.x += horizontal
    if any(rect.colliderect(blocker) for blocker in blockers):
        rect.x -= horizontal

    rect.y += vertical
    if any(rect.colliderect(blocker) for blocker in blockers):
        rect.y -= vertical


def spawning_spiders():
    for spider in MOBS:
        move_spider(spider, player_rect)
    
    
def spider_can_see_player(spider_rect, target_rect):
    start = spider_rect.center
    end = target_rect.center
    return not any(
        wall.clipline(start, end)
        for wall in GAME_MAP.wall_rects
    )


def find_spider_path(spider_rect, destination, other_spiders):
    tile_width, tile_height = GAME_MAP.tile_size
    start = (
        spider_rect.centerx // tile_width,
        spider_rect.centery // tile_height,
    )
    floor_cells = GAME_MAP.floor_cells
    if start not in floor_cells:
        return []

    pending = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    goal = None
    while pending:
        cell = pending.popleft()
        column, row = cell
        center = (
            column * tile_width + tile_width // 2,
            row * tile_height + tile_height // 2,
        )
        if (
            pygame.Vector2(center).distance_to(destination)
            <= max(tile_width, tile_height) * 1.5
            and (
                goal is None
                or pygame.Vector2(center).distance_squared_to(destination)
                < pygame.Vector2(
                    goal[0] * tile_width + tile_width // 2,
                    goal[1] * tile_height + tile_height // 2,
                ).distance_squared_to(destination)
            )
        ):
            goal = cell

        for neighbor in (
            (column + 1, row),
            (column - 1, row),
            (column, row + 1),
            (column, row - 1),
        ):
            if neighbor in previous or neighbor not in floor_cells:
                continue

            center = (
                neighbor[0] * tile_width + tile_width // 2,
                neighbor[1] * tile_height + tile_height // 2,
            )
            waypoint = pygame.Rect((0, 0), spider_rect.size)
            waypoint.center = center
            if (
                not GAME_MAP.is_walkable(waypoint)
                or any(waypoint.colliderect(other) for other in other_spiders)
            ):
                continue

            previous[neighbor] = cell
            pending.append(neighbor)

    if goal is None:
        return []

    path = []
    cell = goal
    while cell is not None:
        path.append(cell)
        cell = previous[cell]
    path.reverse()
    return path


def move_spider(spider, player_rect):
    spider_rect = spider["rect"]
    blockers = [player_rect] + [
        other_spider["rect"] for other_spider in MOBS if other_spider is not spider
    ] + GAME_MAP.wall_rects

    knockback_velocity = spider["knockback_velocity"]
    if knockback_velocity.length_squared() > 0.25:
        move_without_collision(
            spider_rect,
            round(knockback_velocity.x),
            round(knockback_velocity.y),
            blockers,
        )
        knockback_velocity *= KNOCKBACK_FRICTION
        if knockback_velocity.length_squared() <= 0.25:
            spider["knockback_velocity"] = pygame.Vector2()
        return

    spider["knockback_velocity"] = pygame.Vector2()
    if spider_can_see_player(spider_rect, player_rect):
        spider["is_chasing"] = True
        spider["last_known_player_position"] = player_rect.center
    elif not spider["is_chasing"]:
        return

    target = spider["last_known_player_position"]
    other_spiders = [
        other_spider["rect"]
        for other_spider in MOBS
        if other_spider is not spider
    ]
    path = find_spider_path(spider_rect, target, other_spiders)
    if not path:
        return

    tile_width, tile_height = GAME_MAP.tile_size
    if len(path) > 1:
        next_cell = path[1]
        target_x = next_cell[0] * tile_width + tile_width // 2
        target_y = next_cell[1] * tile_height + tile_height // 2
    else:
        target_x, target_y = target

    horizontal = max(
        -spider["speed"],
        min(spider["speed"], target_x - spider_rect.centerx),
    )
    vertical = max(
        -spider["speed"],
        min(spider["speed"], target_y - spider_rect.centery),
    )
    if horizontal > 0:
        spider["image"] = pygame.transform.flip(SPIDER_IMAGE, True, False)
    elif horizontal < 0:
        spider["image"] = SPIDER_IMAGE

    move_without_collision(spider_rect, horizontal, vertical, blockers)
    if (
        not spider_can_see_player(spider_rect, player_rect)
        and pygame.Vector2(spider_rect.center).distance_to(target)
        <= max(tile_width, tile_height)
    ):
        spider["is_chasing"] = False
        spider["last_known_player_position"] = None


def attack_nearby_spider(now):
    global last_player_attack, player_stamina

    if now - last_player_attack < PLAYER_ATTACK_COOLDOWN_MS:
        return

    nearby_spiders = [
        spider for spider in MOBS
        if player_attack_reaches_spider(spider)
    ]
    if not nearby_spiders:
        return
    if player_stamina < PLAYER_ATTACK_STAMINA_COST:
        return

    player_center = pygame.Vector2(player_rect.center)
    for spider in nearby_spiders:
        spider_rect = spider["rect"]
        knockback = pygame.Vector2(spider_rect.center) - player_center
        if knockback.length_squared() == 0:
            knockback = pygame.Vector2(1, 0)
        knockback.scale_to_length(PLAYER_ATTACK_KNOCKBACK_SPEED)

        spider["health"] -= PLAYER_ATTACK_DAMAGE
        spider["knockback_velocity"] = knockback
        spawn_damage_particles(spider_rect.center, (255, 210, 70))
    player_stamina -= PLAYER_ATTACK_STAMINA_COST
    last_player_attack = now


def spider_attack_area(spider):
    return spider["rect"].inflate(
        SPIDER_ATTACK_RANGE * 2,
        SPIDER_ATTACK_RANGE * 2,
    )


def player_attack_reaches_spider(spider):
    spider_area = spider_attack_area(spider)
    closest_x = max(spider_area.left, min(player_rect.centerx, spider_area.right))
    closest_y = max(spider_area.top, min(player_rect.centery, spider_area.bottom))
    offset_x = player_rect.centerx - closest_x
    offset_y = player_rect.centery - closest_y
    return offset_x**2 + offset_y**2 <= PLAYER_ATTACK_RANGE**2


def attack_player_from_spiders(now):
    global player_health

    for spider in MOBS:
        if (
            pygame.Rect(spider["rect"]).inflate(
                SPIDER_ATTACK_RANGE * 2, SPIDER_ATTACK_RANGE * 2
            ).colliderect(player_rect)
            and now >= spider["next_attack_time"]
        ):
            player_health = max(0, player_health - SPIDER_ATTACK_DAMAGE)
            spawn_damage_particles(player_rect.center, (255, 70, 70))
            spider["next_attack_time"] = now + SPIDER_ATTACK_COOLDOWN_MS


def draw_sword_swing(now):
    elapsed = now - last_sword_swing
    if not 0 <= elapsed < PLAYER_SWORD_SWING_DURATION_MS:
        return

    progress = elapsed / PLAYER_SWORD_SWING_DURATION_MS
    center = pygame.Vector2(
        PLAYER_ATTACK_RANGE + 8,
        PLAYER_ATTACK_RANGE + 8,
    )
    facing_angle = math.atan2(
        last_sword_swing_facing.y,
        last_sword_swing_facing.x,
    )
    half_arc = math.radians(PLAYER_SWORD_SWING_ARC_DEGREES / 2)
    start_angle = facing_angle - half_arc
    current_angle = start_angle + progress * half_arc * 2
    swing_surface = pygame.Surface(
        (PLAYER_ATTACK_RANGE * 2 + 16, PLAYER_ATTACK_RANGE * 2 + 16),
        pygame.SRCALPHA,
    )

    trail_start = max(start_angle, current_angle - math.radians(45))
    trail_points = [
        (
            round(center.x + math.cos(angle) * PLAYER_ATTACK_RANGE),
            round(center.y + math.sin(angle) * PLAYER_ATTACK_RANGE),
        )
        for angle in (
            trail_start + (current_angle - trail_start) * step / 8
            for step in range(9)
        )
    ]
    if len(trail_points) > 1:
        pygame.draw.lines(swing_surface, (205, 225, 245, 150), False, trail_points, 3)

    direction = pygame.Vector2(math.cos(current_angle), math.sin(current_angle))
    blade_start = center + direction * 10
    blade_end = center + direction * PLAYER_ATTACK_RANGE
    pygame.draw.line(
        swing_surface,
        (75, 85, 100, 230),
        blade_start,
        blade_end,
        7,
    )
    pygame.draw.line(
        swing_surface,
        (220, 230, 240, 255),
        blade_start,
        blade_end,
        4,
    )
    guard_center = center + direction * 10
    guard_direction = pygame.Vector2(-direction.y, direction.x) * 6
    pygame.draw.line(
        swing_surface,
        (150, 160, 175, 255),
        guard_center - guard_direction,
        guard_center + guard_direction,
        3,
    )
    handle_end = center - direction * 5
    pygame.draw.line(
        swing_surface,
        (100, 65, 40, 255),
        guard_center,
        handle_end,
        4,
    )
    screen.blit(
        swing_surface,
        (
            player_rect.centerx - round(center.x),
            player_rect.centery - round(center.y),
        ),
    )



running = True
while running:
    delta_seconds = clock.tick(FPS) / 1000
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif DEBUG and event.type == pygame.KEYDOWN and event.key == pygame.K_EQUALS:
            spawn_spider()
        elif (
            player_health > 0
            and event.type == pygame.KEYDOWN
            and event.key == pygame.K_SPACE
        ):
            now = pygame.time.get_ticks()
            if now - last_sword_swing >= PLAYER_ATTACK_COOLDOWN_MS:
                last_sword_swing = now
                last_sword_swing_facing = pygame.Vector2(player_facing)
            attack_nearby_spider(now)

    now = pygame.time.get_ticks()
    if player_health > 0:
        is_moving, is_sprinting = movement(delta_seconds)
        update_stamina(delta_seconds, is_moving, is_sprinting, now)
        spawning_spiders()
        attack_player_from_spiders(now)
        MOBS = [spider for spider in MOBS if spider["health"] > 0]

    update_damage_particles(delta_seconds)

    GAME_MAP.draw(screen)

    if DEBUG:
        screen.blit(
            attack_range_indicator,
            (
                player_rect.centerx - PLAYER_ATTACK_RANGE,
                player_rect.centery - PLAYER_ATTACK_RANGE,
            ),
        )
        for spider in MOBS:
            pygame.draw.rect(
                screen,
                (255, 80, 80),
                spider_attack_area(spider),
                1,
            )
        
    screen.blit(PLAYER_IMAGE, player_rect)
    draw_sword_swing(pygame.time.get_ticks())
    if DEBUG:
        pygame.draw.rect(screen, (80, 255, 255), player_rect, 1)

    health_text = font.render(
        f"Health: {player_health}/{PLAYER_MAX_HEALTH}", True, "white"
    )
    screen.blit(health_text, (10, 10))
    stamina_label = font.render("Stamina", True, "white")
    screen.blit(stamina_label, (10, 38))
    stamina_bar = pygame.Rect(10, 65, 200, 12)
    pygame.draw.rect(screen, "darkgray", stamina_bar)
    stamina_bar.width = math.ceil(
        200 * player_stamina / PLAYER_MAX_STAMINA
    )
    pygame.draw.rect(screen, "cyan", stamina_bar)
    stamina_text = font.render(
        f"{math.ceil(player_stamina)}/{PLAYER_MAX_STAMINA}", True, "white"
    )
    screen.blit(stamina_text, (220, 58))
    
    for spider in MOBS:
        screen.blit(spider["image"], spider["rect"])
        health_bar = pygame.Rect(spider["rect"].x, spider["rect"].y - 8, 30, 5)
        pygame.draw.rect(screen, "darkred", health_bar)
        health_bar.width = max(
            0, int(30 * spider["health"] / SPIDER_MAX_HEALTH)
        )
        pygame.draw.rect(screen, "limegreen", health_bar)

    draw_damage_particles()

    if player_health == 0:
        screen.fill("black")
        game_over_text = font.render("GAME OVER", True, "red")
        screen.blit(game_over_text, game_over_text.get_rect(center=screen.get_rect().center))

    pygame.display.flip()




pygame.quit()