from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from database.repositories import Repository
from keyboards.inline import projects_kb, folder_kb, file_kb, component_kb, component_file_choice_kb, note_kb, confirm_kb
from services.weight import folder_mass, fmt_mass
from services.navigation import folder_path

router = Router()
repo: Repository | None = None

def setup(repository: Repository):
    global repo
    repo = repository

class Form(StatesGroup):
    project_name = State()
    project_limit = State()
    folder_name = State()
    component_name = State()
    component_mass = State()
    component_qty = State()
    note_text = State()
    waiting_file = State()
    file_mass = State()
    file_comment = State()
    file_qty = State()
    component_waiting_file = State()
    component_file_comment = State()

async def edit_or_answer(event, text, markup=None):
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=markup)
        except Exception:
            await event.message.answer(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)

async def show_projects(event, user_id):
    ps = await repo.list_projects(user_id)
    await edit_or_answer(event, "Инженерное хранилище\n\nВыберите проект:", projects_kb(ps))

async def show_folder(event, folder_id, user_id):
    if not await repo.folder_owned(folder_id, user_id):
        return await edit_or_answer(event, "Нет доступа.")
    folder = await repo.get_folder(folder_id)
    project = await repo.get_project(folder["project_id"], user_id)
    folders, files, comps, notes = await repo.list_folder_content(folder_id)
    mass = await folder_mass(repo, folder_id)
    path = await folder_path(repo, folder_id)
    title = f"📦 {project['name']}"
    if path:
        title += f"\n› {path}"
    title += f"\n\n⚖️ {fmt_mass(mass)}"
    if folder["parent_id"] is None and project["weight_limit_g"] is not None:
        limit = float(project["weight_limit_g"])
        title += f" / {fmt_mass(limit)}\nЗапас: {fmt_mass(limit-mass)}"
    title += "\n\nВыберите элемент:"
    await edit_or_answer(event, title, folder_kb(folder, folders, files, comps, notes, folder["parent_id"] is None))

@router.callback_query(F.data == "projects")
async def projects(c: CallbackQuery):
    await show_projects(c, c.from_user.id)

@router.callback_query(F.data == "project_new")
async def project_new(c: CallbackQuery, state: FSMContext):
    await state.set_state(Form.project_name)
    await c.message.answer("Название нового проекта:")
    await c.answer()

@router.message(Form.project_name)
async def project_name(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if not name:
        return await m.answer("Введите непустое название.")
    pid = await repo.create_project(m.from_user.id, name)
    await state.clear()
    root = await repo.root_folder(pid)
    await show_folder(m, root["id"], m.from_user.id)

@router.callback_query(F.data.startswith("project:"))
async def project_open(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await repo.get_project(pid, c.from_user.id)
    if not p:
        return await c.answer("Нет доступа", show_alert=True)
    root = await repo.root_folder(pid)
    await show_folder(c, root["id"], c.from_user.id)

@router.callback_query(F.data.startswith("project_settings:"))
async def project_settings(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await repo.get_project(pid, c.from_user.id)
    if not p:
        return await c.answer("Нет доступа", show_alert=True)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚖️ Задать лимит массы", callback_data=f"project_limit:{pid}")],
        [InlineKeyboardButton(text="🗑 Удалить проект", callback_data=f"project_deleteask:{pid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"project:{pid}")]
    ])
    await edit_or_answer(c, f"⚙️ {p['name']}\nЛимит: {fmt_mass(p['weight_limit_g'])}", kb)

@router.callback_query(F.data.startswith("project_limit:"))
async def project_limit(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    await state.update_data(project_id=pid)
    await state.set_state(Form.project_limit)
    await c.message.answer("Введите лимит в граммах или 0, чтобы убрать:")
    await c.answer()

@router.message(Form.project_limit)
async def project_limit_value(m: Message, state: FSMContext):
    try:
        x = float((m.text or "").replace(",", "."))
        if x < 0: raise ValueError
    except ValueError:
        return await m.answer("Нужно неотрицательное число.")
    data = await state.get_data()
    pid = data["project_id"]
    await repo.set_project_limit(pid, m.from_user.id, None if x == 0 else x)
    await state.clear()
    root = await repo.root_folder(pid)
    await show_folder(m, root["id"], m.from_user.id)

@router.callback_query(F.data.startswith("project_deleteask:"))
async def project_deleteask(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    await edit_or_answer(c, "Удалить проект целиком?", confirm_kb(f"project_delete:{pid}", f"project:{pid}"))

@router.callback_query(F.data.startswith("project_delete:"))
async def project_delete(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    await repo.delete_project(pid, c.from_user.id)
    await show_projects(c, c.from_user.id)

@router.callback_query(F.data.startswith("folder:"))
async def folder_open(c: CallbackQuery):
    await show_folder(c, int(c.data.split(":")[1]), c.from_user.id)

@router.callback_query(F.data.startswith("folder_new:"))
async def folder_new(c: CallbackQuery, state: FSMContext):
    parent = int(c.data.split(":")[1])
    f = await repo.get_folder(parent)
    await state.update_data(parent_id=parent, project_id=f["project_id"])
    await state.set_state(Form.folder_name)
    await c.message.answer("Название папки:")
    await c.answer()

@router.message(Form.folder_name)
async def folder_name(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if not name: return await m.answer("Введите название.")
    d = await state.get_data()
    await repo.create_folder(d["project_id"], d["parent_id"], name)
    await state.clear()
    await show_folder(m, d["parent_id"], m.from_user.id)

@router.callback_query(F.data.startswith("folder_settings:"))
async def folder_settings(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    f = await repo.get_folder(fid)
    await edit_or_answer(c, f"⚙️ Папка «{f['name']}»", confirm_kb(f"folder_delete:{fid}", f"folder:{fid}"))

@router.callback_query(F.data.startswith("folder_delete:"))
async def folder_delete(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    f = await repo.get_folder(fid)
    parent = f["parent_id"]
    await repo.delete_folder(fid)
    await show_folder(c, parent, c.from_user.id)

## @brief Начинает процесс создания новой детали.
#
#  @param c Callback-запрос от Telegram.
#  @param state Текущее FSM-состояние пользователя.
#
#  @details
#  Функция получает идентификатор текущей папки,
#  сохраняет его в FSM и переводит пользователя
#  к этапу ввода названия детали.
@router.callback_query(F.data.startswith("component_new:"))
async def component_new(c: CallbackQuery, state: FSMContext):
    folder_id = int(c.data.split(":")[1])
    await state.update_data(folder_id=folder_id, creating_component=True)
    await state.set_state(Form.component_name)
    await c.message.answer("Название компонента:")
    await c.answer()

@router.message(Form.component_name)
async def component_name_value(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if not name: return await m.answer("Введите название.")
    d = await state.get_data()
    if d.get("creating_component"):
        cid = await repo.create_component(d["folder_id"], name)
        await state.update_data(component_id=cid, creating_component=False)
        await state.set_state(Form.component_mass)
        await m.answer("Масса одного экземпляра в граммах? Отправьте 0, если масса неизвестна.")
    else:
        cid = d["component_id"]
        c = await repo.get_component(cid)
        await repo.update_component(cid, name=name)
        await state.clear()
        await show_folder(m, c["folder_id"], m.from_user.id)
## @brief Обрабатывает введённую пользователем массу детали.
#
#  @param m Сообщение Telegram с введённым значением массы.
#  @param state Текущее FSM-состояние пользователя.
#
#  @details
#  Функция преобразует введённое значение в число,
#  проверяет корректность и сохраняет массу детали.
#  При некорректном вводе пользователю выводится сообщение об ошибке.
@router.message(Form.component_mass)
async def component_mass_value(m: Message, state: FSMContext):
    try:
        x = float((m.text or "").replace(",", "."))
        if x < 0: raise ValueError
    except ValueError:
        return await m.answer("Введите число ≥ 0.")
    d = await state.get_data()
    cid = d["component_id"]
    await repo.update_component(cid, mass_marker=True, mass_g=None if x == 0 else x)
    if d.get("editing_component_mass"):
        c = await repo.get_component(cid)
        await state.clear()
        return await show_folder(m, c["folder_id"], m.from_user.id)
    await state.set_state(Form.component_qty)
    await m.answer("Количество экземпляров?")

@router.message(Form.component_qty)
async def component_qty_value(m: Message, state: FSMContext):
    try:
        q = int(m.text or "")
        if q < 1: raise ValueError
    except ValueError:
        return await m.answer("Введите целое число ≥ 1.")
    d = await state.get_data()
    cid = d["component_id"]
    c = await repo.get_component(cid)
    await repo.update_component(cid, quantity=q)
    if d.get("editing_component_qty"):
        await state.clear()
        return await show_folder(m, c["folder_id"], m.from_user.id)
    await state.clear()
    await m.answer(
        "Приложить файл к детали? Если файла нет, выберите «— Без файла».",
        reply_markup=component_file_choice_kb(cid)
    )

@router.callback_query(F.data.startswith("component:"))
async def component_open(c: CallbackQuery):
    cid = int(c.data.split(":")[1])
    if not await repo.component_owned(cid, c.from_user.id): return await c.answer("Нет доступа", show_alert=True)
    x = await repo.get_component(cid)
    total = (x["mass_g"] or 0) * x["quantity"] if x["mass_g"] is not None else None
    versions = await repo.list_component_file_versions(cid)
    text = f"🔩 {x['name']}\n\nМасса: {fmt_mass(x['mass_g'])}\nКоличество: {x['quantity']}"
    if total is not None: text += f"\nВсего: {fmt_mass(total)}"
    if versions:
        text += f"\n\nФайл: {versions[0]['file_name']} · v{versions[0]['version_number']}"
        text += f"\nВерсий: {len(versions)}"
    else:
        text += "\n\nФайл: —"
    await edit_or_answer(c, text, component_kb(cid, x["folder_id"], versions))

@router.callback_query(F.data.startswith("component_mass:"))
async def component_mass(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.split(":")[1])
    await state.update_data(component_id=cid, editing_component_mass=True)
    await state.set_state(Form.component_mass)
    await c.message.answer("Новая масса в граммах; 0 = неизвестна:")
    await c.answer()

@router.callback_query(F.data.startswith("component_qty:"))
async def component_qty(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.split(":")[1])
    await state.update_data(component_id=cid, editing_component_qty=True)
    await state.set_state(Form.component_qty)
    await c.message.answer("Новое количество:")
    await c.answer()

@router.callback_query(F.data.startswith("component_name:"))
async def component_name(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.split(":")[1])
    await state.update_data(component_id=cid, creating_component=False)
    await state.set_state(Form.component_name)
    await c.message.answer("Новое название:")
    await c.answer()

@router.callback_query(F.data.startswith("component_deleteask:"))
async def component_deleteask(c: CallbackQuery):
    cid = int(c.data.split(":")[1])
    await edit_or_answer(c, "Удалить деталь и все версии её файла?", confirm_kb(f"component_delete:{cid}", f"component:{cid}"))

@router.callback_query(F.data.startswith("component_delete:"))
async def component_delete(c: CallbackQuery):
    cid = int(c.data.split(":")[1])
    x = await repo.get_component(cid)
    await repo.delete_component(cid)
    await show_folder(c, x["folder_id"], c.from_user.id)

@router.callback_query(F.data.startswith("component_nofile:"))
async def component_nofile(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.split(":")[1])
    if not await repo.component_owned(cid, c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    x = await repo.get_component(cid)
    await state.clear()
    await show_folder(c, x["folder_id"], c.from_user.id)

@router.callback_query(F.data.startswith("component_attach:"))
async def component_attach(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.split(":")[1])
    if not await repo.component_owned(cid, c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await state.update_data(component_id=cid)
    await state.set_state(Form.component_waiting_file)
    await c.message.answer("Отправьте файл детали как документ.")
    await c.answer()

@router.message(Form.component_waiting_file, F.document)
async def component_receive_file(m: Message, state: FSMContext):
    d = await state.get_data()
    doc = m.document
    await state.update_data(
        component_file_name=doc.file_name,
        component_tg_file_id=doc.file_id,
        component_unique_id=doc.file_unique_id,
        component_file_size=doc.file_size,
    )
    await state.set_state(Form.component_file_comment)
    await m.answer("Комментарий к этой версии? Отправьте «-», если не нужен.")

@router.message(Form.component_waiting_file)
async def component_receive_not_file(m: Message):
    await m.answer("Нужно отправить именно файл/документ.")

@router.message(Form.component_file_comment)
async def component_file_comment(m: Message, state: FSMContext):
    d = await state.get_data()
    comment = (m.text or "").strip()
    if comment == "-":
        comment = None
    _, version = await repo.add_component_file_version(
        d["component_id"], d["component_file_name"], d["component_tg_file_id"],
        d["component_unique_id"], d["component_file_size"], comment
    )
    x = await repo.get_component(d["component_id"])
    await state.clear()
    await m.answer(f"Файл сохранён как v{version} детали «{x['name']}».")
    await show_folder(m, x["folder_id"], m.from_user.id)

@router.callback_query(F.data.startswith("component_version_send:"))
async def component_version_send(c: CallbackQuery):
    vid = int(c.data.split(":")[1])
    v = await repo.get_component_file_version(vid)
    if not v:
        return await c.answer("Версия не найдена", show_alert=True)
    x = await repo.get_component(v["component_id"])
    if not await repo.component_owned(x["id"], c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    caption = f"{x['name']} · v{v['version_number']}"
    if v["comment"]:
        caption += f"\n{v['comment']}"
    await c.message.answer_document(v["telegram_file_id"], caption=caption)
    await c.answer()

@router.callback_query(F.data.startswith("note_new:"))
async def note_new(c: CallbackQuery, state: FSMContext):
    fid = int(c.data.split(":")[1])
    await state.update_data(folder_id=fid)
    await state.set_state(Form.note_text)
    await c.message.answer("Текст записки:")
    await c.answer()

@router.message(Form.note_text)
async def note_text(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    if not text: return await m.answer("Записка не может быть пустой.")
    d = await state.get_data()
    await repo.create_note(d["folder_id"], m.from_user.id, text)
    await state.clear()
    await show_folder(m, d["folder_id"], m.from_user.id)

@router.callback_query(F.data.startswith("note:"))
async def note_open(c: CallbackQuery):
    nid = int(c.data.split(":")[1])
    if not await repo.note_owned(nid, c.from_user.id): return await c.answer("Нет доступа", show_alert=True)
    n = await repo.get_note(nid)
    await edit_or_answer(c, f"📝 {n['created_at']}\n\n{n['text']}", note_kb(nid, n["folder_id"]))

@router.callback_query(F.data.startswith("note_deleteask:"))
async def note_deleteask(c: CallbackQuery):
    nid = int(c.data.split(":")[1])
    n = await repo.get_note(nid)
    await edit_or_answer(c, "Удалить записку?", confirm_kb(f"note_delete:{nid}", f"note:{nid}"))

@router.callback_query(F.data.startswith("note_delete:"))
async def note_delete(c: CallbackQuery):
    nid = int(c.data.split(":")[1])
    n = await repo.get_note(nid)
    await repo.delete_note(nid)
    await show_folder(c, n["folder_id"], c.from_user.id)

@router.callback_query(F.data.startswith("file_upload:"))
async def file_upload(c: CallbackQuery, state: FSMContext):
    fid = int(c.data.split(":")[1])
    await state.update_data(folder_id=fid, forced_file_id=None)
    await state.set_state(Form.waiting_file)
    await c.message.answer("Отправьте файл как документ.")
    await c.answer()

@router.callback_query(F.data.startswith("file_newver:"))
async def file_newver(c: CallbackQuery, state: FSMContext):
    file_id = int(c.data.split(":")[1])
    f = await repo.get_file(file_id)
    await state.update_data(folder_id=f["folder_id"], forced_file_id=file_id)
    await state.set_state(Form.waiting_file)
    await c.message.answer(f"Отправьте новую версию файла «{f['name']}».")
    await c.answer()

@router.message(Form.waiting_file, F.document)
async def receive_file(m: Message, state: FSMContext):
    d = await state.get_data()
    doc = m.document
    target = d.get("forced_file_id")
    if target is None:
        existing = await repo.find_file_by_name(d["folder_id"], doc.file_name)
        if existing:
            target = existing["id"]
        else:
            target = await repo.create_file(d["folder_id"], doc.file_name)
    latest = await repo.latest_version(target)
    await state.update_data(
        target_file_id=target,
        tg_file_id=doc.file_id,
        unique_id=doc.file_unique_id,
        size=doc.file_size,
        inherited_mass=latest["mass_g"] if latest else None,
    )
    await state.set_state(Form.file_mass)
    hint = f" (предыдущая: {fmt_mass(latest['mass_g'])})" if latest else ""
    await m.answer("Масса этой версии в граммах? 0 = без массы" + hint)

@router.message(Form.waiting_file)
async def receive_not_file(m: Message):
    await m.answer("Нужно отправить именно файл/документ.")

@router.message(Form.file_mass)
async def file_mass_value(m: Message, state: FSMContext):
    try:
        x = float((m.text or "").replace(",", "."))
        if x < 0: raise ValueError
    except ValueError:
        return await m.answer("Введите число ≥ 0.")
    await state.update_data(new_mass=None if x == 0 else x)
    await state.set_state(Form.file_comment)
    await m.answer("Комментарий к версии? Отправьте «-», если не нужен.")

@router.message(Form.file_comment)
async def file_comment_value(m: Message, state: FSMContext):
    d = await state.get_data()
    comment = (m.text or "").strip()
    if comment == "-": comment = None
    vid, n = await repo.add_file_version(
        d["target_file_id"], d["tg_file_id"], d["unique_id"], d["size"], d["new_mass"], comment
    )
    f = await repo.get_file(d["target_file_id"])
    await state.clear()
    await m.answer(f"Сохранено как v{n}.")
    await show_folder(m, f["folder_id"], m.from_user.id)

@router.callback_query(F.data.startswith("file:"))
async def file_open(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    if not await repo.file_owned(fid, c.from_user.id): return await c.answer("Нет доступа", show_alert=True)
    f = await repo.get_file(fid)
    versions = await repo.list_versions(fid)
    latest = versions[0] if versions else None
    text = f"📄 {f['name']}\n\nКоличество: {f['quantity']}"
    if latest:
        text += f"\nТекущая версия: v{latest['version_number']}\nМасса: {fmt_mass(latest['mass_g'])}"
        if latest["mass_g"] is not None:
            text += f"\nВсего: {fmt_mass(latest['mass_g'] * f['quantity'])}"
    text += "\n\nИстория версий:"
    await edit_or_answer(c, text, file_kb(fid, f["folder_id"], versions))

@router.callback_query(F.data.startswith("version_send:"))
async def version_send(c: CallbackQuery):
    vid = int(c.data.split(":")[1])
    v = await repo.get_version(vid)
    f = await repo.get_file(v["file_id"])
    if not await repo.file_owned(f["id"], c.from_user.id): return await c.answer("Нет доступа", show_alert=True)
    caption = f"{f['name']} · v{v['version_number']}\nМасса: {fmt_mass(v['mass_g'])}"
    if v["comment"]: caption += f"\n{v['comment']}"
    await c.message.answer_document(v["telegram_file_id"], caption=caption)
    await c.answer()

@router.callback_query(F.data.startswith("file_qty:"))
async def file_qty(c: CallbackQuery, state: FSMContext):
    fid = int(c.data.split(":")[1])
    await state.update_data(file_id=fid)
    await state.set_state(Form.file_qty)
    await c.message.answer("Количество экземпляров:")
    await c.answer()

@router.message(Form.file_qty)
async def file_qty_value(m: Message, state: FSMContext):
    try:
        q = int(m.text or "")
        if q < 1: raise ValueError
    except ValueError:
        return await m.answer("Введите целое число ≥ 1.")
    d = await state.get_data()
    f = await repo.get_file(d["file_id"])
    await repo.set_file_quantity(f["id"], q)
    await state.clear()
    await show_folder(m, f["folder_id"], m.from_user.id)

@router.callback_query(F.data.startswith("file_deleteask:"))
async def file_deleteask(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    await edit_or_answer(c, "Удалить файл и всю историю его версий?", confirm_kb(f"file_delete:{fid}", f"file:{fid}"))

@router.callback_query(F.data.startswith("file_delete:"))
async def file_delete(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    f = await repo.get_file(fid)
    await repo.delete_file(fid)
    await show_folder(c, f["folder_id"], c.from_user.id)
