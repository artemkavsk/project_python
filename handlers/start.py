from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from database.repositories import Repository
from keyboards.inline import projects_kb

router = Router()
repo: Repository | None = None

def setup(repository: Repository):
    global repo
    repo = repository

@router.message(CommandStart())
@router.message(Command("projects"))
async def start(message: Message):
    await repo.ensure_user(message.from_user.id)
    projects = await repo.list_projects(message.from_user.id)
    await message.answer(
        "Инженерное хранилище\n\nВыберите проект или создайте новый.",
        reply_markup=projects_kb(projects)
    )
