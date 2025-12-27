from pythonforandroid.recipe import Recipe
import shutil
from os.path import join, dirname

class MonerodRecipe(Recipe):
    name = 'monerod'
    version = 'v0.18.4.4'
    
    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        recipe_dir = dirname(__file__)
        lib_dir = join(self.ctx.get_libs_dir(arch.arch))
        shutil.copy(
            join(recipe_dir, 'libmonerod_arm32.so'),
            join(lib_dir, 'libmonerod_arm32.so')
        )

        shutil.copy(
            join(recipe_dir, 'libmonerod_arm64.so'),
            join(lib_dir, 'libmonerod_arm64.so')
        )


recipe = MonerodRecipe()
