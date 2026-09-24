from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def projects_kb(projects):
    b = InlineKeyboardBuilder()
    for p in projects:
        b.row(InlineKeyboardButton(text=f"📦 {p['name']}", callback_data=f"project:{p['id']}"))
    b.row(InlineKeyboardButton(text="➕ Создать проект", callback_data="project_new"))
    return b.as_markup()

def folder_kb(folder, folders, files, components, notes, is_root=False):
    b = InlineKeyboardBuilder()
    for x in folders:
        b.row(InlineKeyboardButton(text=f"📁 {x['name']}", callback_data=f"folder:{x['id']}"))
    for x in files:
        v = x["current_version"] or 0
        b.row(InlineKeyboardButton(text=f"📄 {x['name']} · v{v}", callback_data=f"file:{x['id']}"))
    for x in components:
        b.row(InlineKeyboardButton(text=f"⚙️ {x['name']}", callback_data=f"component:{x['id']}"))
    for x in notes[:10]:
        preview = x["text"].replace("\n", " ")[:32]
        b.row(InlineKeyboardButton(text=f"📝 {preview}", callback_data=f"note:{x['id']}"))
    b.row(
        InlineKeyboardButton(text="📁 +", callback_data=f"folder_new:{folder['id']}"),
        InlineKeyboardButton(text="⚙️ +", callback_data=f"component_new:{folder['id']}"),
        InlineKeyboardButton(text="📝 +", callback_data=f"note_new:{folder['id']}"),
    )
    b.row(InlineKeyboardButton(text="📎 Добавить файл", callback_data=f"file_upload:{folder['id']}"))
    if is_root:
        b.row(
            InlineKeyboardButton(text="⚙️ Проект", callback_data=f"project_settings:{folder['project_id']}"),
            InlineKeyboardButton(text="🏠 Проекты", callback_data="projects")
        )
    else:
        b.row(
            InlineKeyboardButton(text="⚙️ Папка", callback_data=f"folder_settings:{folder['id']}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"folder:{folder['parent_id']}")
        )
    return b.as_markup()

def file_kb(file_id, folder_id, versions):
    b = InlineKeyboardBuilder()
    for v in versions[:15]:
        mass = "—" if v["mass_g"] is None else f"{v['mass_g']:g} г"
        b.row(InlineKeyboardButton(
            text=f"v{v['version_number']} · {mass} · скачать",
            callback_data=f"version_send:{v['id']}"
        ))
    b.row(InlineKeyboardButton(text="📎 Новая версия", callback_data=f"file_newver:{file_id}"))
    b.row(
        InlineKeyboardButton(text="🔢 Количество", callback_data=f"file_qty:{file_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"file_deleteask:{file_id}")
    )
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"folder:{folder_id}"))
    return b.as_markup()

def component_kb(cid, folder_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚖️ Масса", callback_data=f"component_mass:{cid}"),
            InlineKeyboardButton(text="🔢 Количество", callback_data=f"component_qty:{cid}")
        ],
        [InlineKeyboardButton(text="✏️ Имя", callback_data=f"component_name:{cid}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"component_deleteask:{cid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"folder:{folder_id}")]
    ])

def note_kb(note_id, folder_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"note_deleteask:{note_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"folder:{folder_id}")]
    ])

def confirm_kb(yes_data, no_data):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_data)
    ]])
