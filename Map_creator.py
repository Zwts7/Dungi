import math
import random
from pathlib import Path

import pygame


class TileMap:
    def __init__(self, size):
        width, height = size
        tile_directory = Path(__file__).resolve().parent / "Tiles"
        tile_paths = sorted(tile_directory.glob("*.png"))
        if not tile_paths:
            raise FileNotFoundError(f"No tile images found in {tile_directory}")

        self.tiles = [
            pygame.image.load(str(tile_path)).convert()
            for tile_path in tile_paths
        ]
        tile_width, tile_height = self.tiles[0].get_size()
        if any(
            tile.get_size() != (tile_width, tile_height)
            for tile in self.tiles
        ):
            raise ValueError("All map tiles must have the same dimensions")

        columns = math.ceil(width / tile_width)
        rows = math.ceil(height / tile_height)
        if columns < 3 or rows < 3:
            raise ValueError("The screen must fit at least three tiles per side")

        right_border_x = (columns - 1) * tile_width
        bottom_border_y = (rows - 1) * tile_height
        self.playable_rect = pygame.Rect(
            tile_width,
            tile_height,
            right_border_x - tile_width,
            bottom_border_y - tile_height,
        )
        self.wall_rects = []
        self.surface = pygame.Surface(size)
        tile_random = random.Random()

        for row in range(rows):
            for column in range(columns):
                x = column * tile_width
                y = row * tile_height
                self.surface.blit(tile_random.choice(self.tiles), (x, y))
                if (
                    row == 0
                    or row == rows - 1
                    or column == 0
                    or column == columns - 1
                ):
                    self.wall_rects.append(
                        pygame.Rect(x, y, tile_width, tile_height)
                    )

    def draw(self, surface):
        surface.blit(self.surface, (0, 0))


def create_map(size):
    return TileMap(size)