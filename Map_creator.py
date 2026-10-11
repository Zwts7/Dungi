import math
import random
from pathlib import Path

import pygame


BORDER_COLOR = (102, 96, 123)
TILE_FILES = {
    "floor": "tile.png",
}
WALL_COLORS = (
    (76, 70, 91),
    (84, 77, 100),
    (92, 84, 108),
)
WALL_HIGHLIGHT = (119, 109, 137)


class TileMap:
    def __init__(self, size):
        width, height = size
        tile_directory = Path(__file__).resolve().parent / "Tiles"
        floor_path = tile_directory / TILE_FILES["floor"]
        if not floor_path.is_file():
            raise FileNotFoundError(
                f"Missing floor tile: {floor_path}"
            )

        self.tiles = {
            name: pygame.image.load(
                str(tile_directory / filename)
            ).convert()
            for name, filename in TILE_FILES.items()
        }
        tile_width, tile_height = self.tiles["floor"].get_size()

        self.columns = width // tile_width
        self.rows = height // tile_height
        if self.columns < 8 or self.rows < 8:
            raise ValueError("The screen must fit at least 8 tiles per side")

        self.tile_size = (tile_width, tile_height)
        self.floor_cells = set()
        self._generate_caves()
        self._build_surface(size)

        floor_columns = [column for column, _ in self.floor_cells]
        floor_rows = [row for _, row in self.floor_cells]
        self.playable_rect = pygame.Rect(
            min(floor_columns) * tile_width,
            min(floor_rows) * tile_height,
            (max(floor_columns) - min(floor_columns) + 1) * tile_width,
            (max(floor_rows) - min(floor_rows) + 1) * tile_height,
        )

    def _carve_chamber(self, center_x, center_y, radius_x, radius_y):
        for row in range(
            max(2, center_y - radius_y),
            min(self.rows - 2, center_y + radius_y + 1),
        ):
            for column in range(
                max(2, center_x - radius_x),
                min(self.columns - 2, center_x + radius_x + 1),
            ):
                dx = (column - center_x) / max(1, radius_x)
                dy = (row - center_y) / max(1, radius_y)
                if dx * dx + dy * dy <= 1.5:
                    self.floor_cells.add((column, row))

    def _carve_tunnel(self, start, direction, length, radius):
        center_x, center_y = start
        angle = direction
        for _ in range(length):
            center_x += round(math.cos(angle))
            center_y += round(math.sin(angle))
            if not 2 <= center_x < self.columns - 2:
                angle = math.pi - angle
                center_x = min(max(center_x, 2), self.columns - 3)
            if not 2 <= center_y < self.rows - 2:
                angle = -angle
                center_y = min(max(center_y, 2), self.rows - 3)
            angle += random.uniform(-0.35, 0.35)
            for row in range(
                max(2, center_y - radius),
                min(self.rows - 2, center_y + radius + 1),
            ):
                for column in range(
                    max(2, center_x - radius),
                    min(self.columns - 2, center_x + radius + 1),
                ):
                    self.floor_cells.add((column, row))
        return center_x, center_y

    def _generate_caves(self):
        center = (self.columns // 2, self.rows // 2)
        large_room = random.random() < 0.5
        if large_room:
            room_radius_x = random.randint(
                5,
                max(5, min(10, self.columns // 6)),
            )
            room_radius_y = random.randint(
                3,
                max(3, min(6, self.rows // 6)),
            )
        else:
            room_radius_x = random.randint(3, 5)
            room_radius_y = random.randint(2, 4)
        self._carve_chamber(center[0], center[1], room_radius_x, room_radius_y)

        branch_count = random.randint(3, 7)
        cave_centers = [center]
        for _ in range(branch_count):
            start = random.choice(cave_centers)
            direction = random.uniform(0, math.tau)
            length = random.randint(
                5,
                max(5, min(self.columns, self.rows) // 2),
            )
            tunnel_radius = random.choice((1, 1, 2))
            endpoint = self._carve_tunnel(
                start,
                direction,
                length,
                tunnel_radius,
            )
            if random.random() < 0.75:
                radius_x = random.randint(2, max(2, min(7, self.columns // 8)))
                radius_y = random.randint(2, max(2, min(5, self.rows // 8)))
                self._carve_chamber(endpoint[0], endpoint[1], radius_x, radius_y)
            cave_centers.append(endpoint)

        self.exterior_cells = self._fill_enclosed_pockets()

    def _fill_enclosed_pockets(self):
        exterior = set()
        pending = [
            (column, row)
            for column in range(self.columns)
            for row in (0, self.rows - 1)
        ]
        pending.extend(
            (column, row)
            for row in range(1, self.rows - 1)
            for column in (0, self.columns - 1)
        )

        while pending:
            cell = pending.pop()
            column, row = cell
            if (
                cell in exterior
                or cell in self.floor_cells
                or not (0 <= column < self.columns and 0 <= row < self.rows)
            ):
                continue
            exterior.add(cell)
            pending.extend(
                (
                    (column + 1, row),
                    (column - 1, row),
                    (column, row + 1),
                    (column, row - 1),
                )
            )

        for row in range(self.rows):
            for column in range(self.columns):
                cell = (column, row)
                if cell not in exterior:
                    self.floor_cells.add(cell)
        return exterior

    def _draw_wall_tile(self, column, row, tile_width, tile_height):
        left = column * tile_width
        top = row * tile_height
        tile_rect = pygame.Rect(left, top, tile_width, tile_height)
        rng = random.Random((column * 73856093) ^ (row * 19349663))
        base_color = rng.choice(WALL_COLORS)
        self.surface.fill(base_color, tile_rect)

        inset = max(2, min(tile_width, tile_height) // 8)
        points = [
            (left + inset + rng.randint(0, inset), top + inset),
            (left + tile_width - inset, top + inset + rng.randint(0, inset)),
            (left + tile_width - inset - rng.randint(0, inset), top + tile_height - inset),
            (left + inset, top + tile_height - inset - rng.randint(0, inset)),
        ]
        pygame.draw.polygon(
            self.surface,
            rng.choice(WALL_COLORS),
            points,
        )
        pygame.draw.lines(
            self.surface,
            WALL_HIGHLIGHT,
            True,
            points,
            max(1, min(tile_width, tile_height) // 16),
        )

    def _build_surface(self, size):
        self.surface = pygame.Surface(size)
        self.surface.fill(BORDER_COLOR)
        self.wall_rects = []
        wall_cells = {
            (column + dx, row + dy)
            for column, row in self.floor_cells
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (column + dx, row + dy) not in self.floor_cells
        }
        tile_width, tile_height = self.tile_size

        for column, row in wall_cells:
            position = (column * tile_width, row * tile_height)
            self._draw_wall_tile(column, row, tile_width, tile_height)
            self.wall_rects.append(
                pygame.Rect(position, self.tile_size)
            )
        for column, row in self.floor_cells:
            self.surface.blit(
                self.tiles["floor"],
                (column * tile_width, row * tile_height),
            )

    def draw(self, surface):
        surface.blit(self.surface, (0, 0))

    def is_walkable(self, rect):
        if (
            rect.width <= 0
            or rect.height <= 0
            or rect.left < 0
            or rect.top < 0
            or rect.right > self.surface.get_width()
            or rect.bottom > self.surface.get_height()
        ):
            return False

        tile_width, tile_height = self.tile_size
        first_column = rect.left // tile_width
        last_column = (rect.right - 1) // tile_width
        first_row = rect.top // tile_height
        last_row = (rect.bottom - 1) // tile_height
        return all(
            (column, row) in self.floor_cells
            for row in range(first_row, last_row + 1)
            for column in range(first_column, last_column + 1)
        )


def create_map(size):
    return TileMap(size)
