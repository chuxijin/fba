from fastapi import APIRouter

from backend.app.health.api.v1.food import router as food_router
from backend.app.health.api.v1.food_category import router as food_category_router
from backend.app.health.api.v1.food_tag import router as food_tag_router
from backend.app.health.api.v1.nutrition_fact import router as nutrition_fact_router

router = APIRouter(prefix='/health')

router.include_router(food_category_router, prefix='/categories', tags=['食物分类'])
router.include_router(food_router, prefix='/foods', tags=['食物'])
router.include_router(nutrition_fact_router, prefix='/nutrition-facts', tags=['营养成分'])
router.include_router(food_tag_router, prefix='/tags', tags=['食物标签'])
