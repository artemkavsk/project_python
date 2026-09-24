from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from handlers import context
from handlers.states import Form
from handlers.views import edit_or_answer, show_folder
from keyboards.inline import component_kb, component_file_choice_kb, confirm_kb
from services.weight import fmt_mass

router = Router()
repo = context.repo

def setup(repository):
    global repo
    repo = repository

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
