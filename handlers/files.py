from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from handlers import context
from handlers.states import Form
from handlers.views import edit_or_answer, show_folder
from keyboards.inline import file_kb, confirm_kb
from services.weight import fmt_mass

router = Router()
repo = context.repo

def setup(repository):
    global repo
    repo = repository

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
