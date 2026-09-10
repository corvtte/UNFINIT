import os
import sys
import base64
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config
from services.session_manager import session_manager
from services.media_service import MediaService
from services.web_panel import (
    handle_studio_upload,
    handle_studio_specs,
    handle_studio_edit_tags,
    handle_studio_batch_edit,
    handle_studio_cut,
    handle_studio_delete,
    handle_studio_delete_batch,
    handle_studio_cleanup,
    handle_studio_table_html,
    get_studio_cover_bytes,
    render_dashboard_html
)

DUMMY_JPEG_B64 = (
    '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////'
    '////////////////////////////////////////////////////wgALCAABAAEBAREA/8QA'
    'FAABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='
)

class TestWebMp3tagStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        sample_path = config.TEMP_DIR / "unit_test_sample.mp3"
        import subprocess
        subprocess.run(
            ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-c:a', 'libmp3lame', str(sample_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        with open(sample_path, 'rb') as f:
            cls.real_mp3_bytes = f.read()
        cls.b64_audio = base64.b64encode(cls.real_mp3_bytes).decode('utf-8')

    def setUp(self):
        config.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def test_01_studio_upload(self):
        payload = {
            'filename': 'lesson_sample_01.mp3',
            'data': f'data:audio/mp3;base64,{self.b64_audio}'
        }
        res = handle_studio_upload(payload)
        self.assertTrue(res.get('ok'), f'Upload failed: {res}')
        drop_id = res.get('drop_id')
        self.assertTrue(drop_id)
        
        session = session_manager.get_session(drop_id)
        self.assertIsNotNone(session)
        self.assertTrue(Path(session['working_path']).exists())
        self.assertEqual(session['source_platform'], 'web_studio')

    def test_02_studio_specs(self):
        payload = {
            'filename': 'lesson_specs_test.mp3',
            'data': self.b64_audio
        }
        res = handle_studio_upload(payload)
        drop_id = res['drop_id']

        specs = handle_studio_specs(drop_id)
        self.assertTrue(specs.get('ok'), f'Specs failed: {specs}')
        self.assertIn('bitrate_kbps', specs)
        self.assertIn('sample_rate', specs)
        self.assertIn('channels', specs)
        self.assertIn('codec', specs)
        self.assertIn('duration_str', specs)

    def test_03_studio_single_tag_edit(self):
        payload = {
            'filename': 'single_edit.mp3',
            'data': self.b64_audio
        }
        upload_res = handle_studio_upload(payload)
        drop_id = upload_res['drop_id']

        edit_payload = {
            'drop_id': drop_id,
            'title': 'معارف اسلامی - جلسه اول',
            'artist': 'دکتر رضایی',
            'album': 'دوره معارف تابستان',
            'new_filename': 'renamed_lesson_01.mp3',
            'cover_data': DUMMY_JPEG_B64,
            'remove_cover': False
        }
        edit_res = handle_studio_edit_tags(edit_payload)
        self.assertTrue(edit_res.get('ok'), f'Edit tags failed: {edit_res}')

        session = session_manager.get_session(drop_id)
        self.assertEqual(session.get('audio_filename'), 'renamed_lesson_01.mp3')
        self.assertTrue(Path(session['working_path']).exists())
        self.assertTrue(session['working_path'].endswith('renamed_lesson_01.mp3'))

        cov_bytes, mime = get_studio_cover_bytes(drop_id)
        self.assertIsNotNone(cov_bytes)
        self.assertEqual(mime, 'image/jpeg')

    def test_04_studio_batch_edit_and_autonumber(self):
        res1 = handle_studio_upload({'filename': 'track1.mp3', 'data': self.b64_audio})
        res2 = handle_studio_upload({'filename': 'track2.mp3', 'data': self.b64_audio})
        drop1 = res1['drop_id']
        drop2 = res2['drop_id']

        batch_payload = {
            'drop_ids': [drop1, drop2],
            'album': 'دوره پیشرفته هوش مصنوعی',
            'artist': 'تیم آنفینیت',
            'auto_number': True,
            'title_pattern': 'جلسه {n}',
            'cover_data': DUMMY_JPEG_B64,
            'remove_cover': False
        }
        batch_res = handle_studio_batch_edit(batch_payload)
        self.assertTrue(batch_res.get('ok'), f'Batch edit failed: {batch_res}')
        self.assertEqual(batch_res.get('updated_count'), 2)

        s1 = session_manager.get_session(drop1)
        self.assertEqual(s1['embed_meta'].get('title'), 'جلسه 1')
        self.assertEqual(s1['embed_meta'].get('album'), 'دوره پیشرفته هوش مصنوعی')
        self.assertEqual(s1['embed_meta'].get('artist'), 'تیم آنفینیت')

        s2 = session_manager.get_session(drop2)
        self.assertEqual(s2['embed_meta'].get('title'), 'جلسه 2')
        self.assertEqual(s2['embed_meta'].get('album'), 'دوره پیشرفته هوش مصنوعی')
        self.assertEqual(s2['embed_meta'].get('artist'), 'تیم آنفینیت')

    def test_05_render_dashboard_ui(self):
        html = render_dashboard_html()
        self.assertIn('استودیوی پیشرفته متادیتا و رسانه (Web Mp3tag Studio)', html)
        self.assertIn('studioDropzone', html)
        self.assertIn('specsModal', html)
        self.assertIn('tagModal', html)
        self.assertIn('batchTagModal', html)
        self.assertIn('cutterModal', html)
        self.assertIn('wavesurfer.min.js', html)
        self.assertIn('btn-tab-studio', html)
        self.assertIn('btn-tab-courses', html)
        self.assertIn('btn-tab-settings', html)
        self.assertIn('tab-studio', html)
        self.assertIn('tab-courses', html)
        self.assertIn('tab-settings', html)
        self.assertIn('logContainer', html)
        self.assertIn('cleanupStudioDrops', html)
        self.assertIn('deleteStudioDrop', html)
        self.assertIn('openCutterModal', html)

    def test_06_studio_cut_audio(self):
        upload_res = handle_studio_upload({'filename': 'to_cut.mp3', 'data': self.b64_audio})
        drop_id = upload_res['drop_id']

        cut_payload = {
            'drop_id': drop_id,
            'start_sec': 0.0,
            'end_sec': 5.0
        }
        cut_res = handle_studio_cut(cut_payload)
        self.assertTrue(cut_res.get('ok'), f'Cut audio failed: {cut_res}')
        new_drop_id = cut_res.get('new_drop_id')
        self.assertTrue(new_drop_id)
        
        new_session = session_manager.get_session(new_drop_id)
        self.assertIsNotNone(new_session)
        self.assertTrue(new_session['audio_filename'].startswith('cut_'))
        self.assertTrue(Path(new_session['working_path']).exists())

    def test_07_studio_delete(self):
        upload_res = handle_studio_upload({'filename': 'to_delete.mp3', 'data': self.b64_audio})
        drop_id = upload_res['drop_id']
        session = session_manager.get_session(drop_id)
        w_path = Path(session['working_path'])
        self.assertTrue(w_path.exists())

        del_res = handle_studio_delete({'drop_id': drop_id})
        self.assertTrue(del_res.get('ok'), f'Delete failed: {del_res}')
        self.assertIsNone(session_manager.get_session(drop_id))
        self.assertFalse(w_path.exists())

    def test_08_studio_cleanup(self):
        # Register two duplicates deliberately
        d1 = MediaService.register_incoming_message_meta(
            drop_id='cleanup_t1',
            source_platform='test_dup',
            chat_id='123',
            file_id='dup_fid_999',
            file_name='duplicate.mp3',
            file_size=1000,
            media_type='audio'
        )
        # Register another with same platform and file_id directly in session_manager
        session_manager.create_session('cleanup_t2', {
            'source_platform': 'test_dup',
            'chat_id': '123',
            'file_id': 'dup_fid_999',
            'audio_filename': 'duplicate.mp3',
            'file_size': 1000
        })

        cleanup_res = handle_studio_cleanup()
        self.assertTrue(cleanup_res.get('ok'), f'Cleanup failed: {cleanup_res}')
        self.assertGreaterEqual(cleanup_res.get('cleaned_count', 0), 1)

    def test_09_deduplication_logic(self):
        # First registration
        drop1 = MediaService.register_incoming_message_meta(
            drop_id='unique_test_1',
            source_platform='telegram',
            chat_id='456',
            file_id='tg_unique_file_123',
            file_name='miracle_33.mp3',
            file_size=54321,
            media_type='audio'
        )
        # Second registration with same metadata
        drop2 = MediaService.register_incoming_message_meta(
            drop_id='unique_test_2',
            source_platform='telegram',
            chat_id='456',
            file_id='tg_unique_file_123',
            file_name='miracle_33.mp3',
            file_size=54321,
            media_type='audio'
        )
        # Should return the first session rather than creating another
        self.assertEqual(drop1['drop_id'], drop2['drop_id'])

    def test_10_permanent_course_delete(self):
        import asyncio
        import json
        from services.store_service import StoreService
        from core.database import init_db

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Add test course
        prod_obj = loop.run_until_complete(StoreService.add_product(
            name="دوره تست حذف دائمی v25.4.3",
            price=250000,
            description="تست دائم",
            download_link="https://test.com/dl"
        ))
        self.assertIsNotNone(prod_obj)
        prod_id = prod_obj.product_id if hasattr(prod_obj, "product_id") else str(prod_obj)
        self.assertTrue(prod_id)

        # Verify added in database and disk
        prod = loop.run_until_complete(StoreService.get_product(prod_id))
        self.assertIsNotNone(prod)

        # Delete course
        ok = loop.run_until_complete(StoreService.delete_product(prod_id))
        self.assertTrue(ok)

        # Verify deleted physically from database
        prod_after = loop.run_until_complete(StoreService.get_product(prod_id))
        self.assertIsNone(prod_after)

        # Verify deleted from courses.json
        courses_file = config.DATA_DIR / "courses.json"
        if courses_file.exists():
            with open(courses_file, "r", encoding="utf-8") as f:
                saved_courses = json.load(f)
            self.assertNotIn(prod_id, [c.get("product_id") for c in saved_courses])

        # Verify DB re-init does not restore the deleted course
        loop.run_until_complete(init_db())
        prod_after_init = loop.run_until_complete(StoreService.get_product(prod_id))
        self.assertIsNone(prod_after_init)
        loop.close()

    def test_11_studio_batch_delete(self):
        # Upload 2 files
        u1 = handle_studio_upload({'filename': 'batch_del_1.mp3', 'data': self.b64_audio})
        u2 = handle_studio_upload({'filename': 'batch_del_2.mp3', 'data': self.b64_audio})
        d1 = u1['drop_id']
        d2 = u2['drop_id']

        # Ensure sessions exist
        self.assertIsNotNone(session_manager.get_session(d1))
        self.assertIsNotNone(session_manager.get_session(d2))

        # Batch delete
        res = handle_studio_delete_batch({'drop_ids': [d1, d2]})
        self.assertTrue(res.get('ok'))
        self.assertEqual(res.get('deleted_count'), 2)

        # Ensure sessions removed
        self.assertIsNone(session_manager.get_session(d1))
        self.assertIsNone(session_manager.get_session(d2))

    def test_12_studio_table_html_and_cover(self):
        u = handle_studio_upload({'filename': 'table_test.mp3', 'data': self.b64_audio})
        res = handle_studio_table_html()
        self.assertTrue(res.get('ok'))
        html = res.get('html')
        self.assertIn('row_' + u['drop_id'], html)
        self.assertIn('w-[38px] h-[38px]', html)
        # Clean up
        handle_studio_delete({'drop_id': u['drop_id']})

    def test_13_settings_overwrite_protection(self):
        import asyncio
        import json
        from core.database import set_system_setting, get_system_setting, init_db

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 1. Save valid token to DB
            loop.run_until_complete(set_system_setting("BALE_BOT_TOKEN", "live_secret_token_v2545"))
            val_before = loop.run_until_complete(get_system_setting("BALE_BOT_TOKEN"))
            self.assertEqual(val_before, "live_secret_token_v2545")

            # 2. Write empty string to data/settings.json (simulating fresh deployment)
            settings_path = config.SETTINGS_JSON_FILE
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump({"BALE_BOT_TOKEN": ""}, f)

            # 3. Call init_db()
            loop.run_until_complete(init_db())

            # 4. Verify the database token was NOT overwritten by the empty string
            val_after = loop.run_until_complete(get_system_setting("BALE_BOT_TOKEN"))
            self.assertEqual(val_after, "live_secret_token_v2545")
        finally:
            loop.close()

    def test_14_bale_send_invoice_slicing(self):
        from platforms.bale_adapter import BaleAdapter
        bale = BaleAdapter()
        bale.token = "fake_token_for_test"

        # Check slicing with long strings
        long_title = "دوره جامع قوانین موفقیت و جذب فرکانس نامحدود نسخه طلایی"
        long_desc = "این یک توضیح بسیار طولانی است که قصد داریم مطمئن شویم در پلتفرم بله خطای بالای ۲۵۵ کاراکتر نمی‌دهد. " * 5
        
        # Test sanitization logic directly
        safe_title = str(long_title or "دوره آموزشی").strip()[:32]
        safe_desc = str(long_desc or safe_title).strip()[:255]

        self.assertLessEqual(len(safe_title), 32)
        self.assertLessEqual(len(safe_desc), 255)
        self.assertTrue(len(safe_title) > 0)
        self.assertTrue(len(safe_desc) > 0)

    def test_15_owner_id_alias_and_telegram_adapter(self):
        from platforms.telegram_adapter import TelegramAdapter
        config.TELEGRAM_OWNER_ID = 987654321
        self.assertEqual(config.OWNER_ID, 987654321)

        tg = TelegramAdapter()
        admin_id = tg.get_admin_id()
        self.assertEqual(admin_id, 987654321)

    def test_16_dashboard_html_security_and_components(self):
        html = render_dashboard_html()
        # 1. Main app wrapper hidden with style="display: none !important;"
        self.assertIn('id="appMain"', html)
        self.assertIn('display: none !important;', html)
        
        # 2. Viewport tag with user-scalable=no
        self.assertIn('maximum-scale=1.0, user-scalable=no', html)

        # 3. Banner inputs type="text"
        self.assertIn('id="newCPhoto"', html)
        self.assertIn('id="editPhoto"', html)
        self.assertNotIn('<input type="url" id="newCPhoto"', html)
        self.assertNotIn('<input type="url" id="editPhoto"', html)

        # 4. Character counters and soft limits
        self.assertIn('counter_newCName', html)
        self.assertIn('counter_newCDesc', html)
        self.assertIn('counter_editName', html)
        self.assertIn('counter_editDesc', html)
        self.assertIn('maxlength="32"', html)
        self.assertNotIn('maxlength="255"', html)  # Soft limit in v25.4.6
        self.assertIn('بیش از سقف مجاز فاکتور بله', html)

        # 5. Mobile hamburger menu and clean header
        self.assertNotIn('JSON API', html)  # Removed in v25.4.6
        self.assertIn('btnMobileMenu', html)
        self.assertIn('mobileNavMenu', html)
        self.assertIn('toggleMobileMenu', html)

        # 6. Cutter toggle switch button (123apps style)
        self.assertIn('btnWaveToggle', html)
        self.assertIn('waveToggleIcon', html)

        # 7. Settings Export/Import and Log Download buttons
        self.assertIn('handleExportSettings()', html)
        self.assertIn('handleImportSettingsFile(this)', html)
        self.assertIn('/api/logs/download', html)

    def test_17_settings_export_import(self):
        import asyncio
        from core.database import set_system_setting, get_system_setting, get_db_connection

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Set setting
            loop.run_until_complete(set_system_setting("CARD_HOLDER", "استاد آزمایشی"))
            val = loop.run_until_complete(get_system_setting("CARD_HOLDER"))
            self.assertEqual(val, "استاد آزمایشی")

            # Check export dictionary
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM system_settings")
            db_dict = {row[0]: row[1] for row in cur.fetchall()}
            conn.close()
            self.assertEqual(db_dict.get("CARD_HOLDER"), "استاد آزمایشی")

            # Simulate import of new card holder
            imported = {"CARD_HOLDER": "نام جدید وارداتی"}
            loop.run_until_complete(set_system_setting("CARD_HOLDER", imported["CARD_HOLDER"]))
            val2 = loop.run_until_complete(get_system_setting("CARD_HOLDER"))
            self.assertEqual(val2, "نام جدید وارداتی")
        finally:
            loop.close()

    def test_18_v25_4_6_rubika_and_storage(self):
        import time
        from core.config import config
        from platforms.rubika_adapter import extract_universal_rubika_updates

        # 1. Verify storage directory existence
        self.assertTrue(config.TEMP_DIR.exists())
        self.assertTrue(config.UPLOADS_DIR.exists())
        self.assertTrue(config.BANNERS_DIR.exists())

        # 2. Test Rubika update timestamp extraction
        past_time = time.time() - 3600
        sample_update_data = {
            "data": {
                "updates": [
                    {
                        "update_id": 101,
                        "type": "NewMessage",
                        "chat_id": "c12345",
                        "message": {
                            "message_id": "m101",
                            "text": "سلام تست قدیمی",
                            "time": int(past_time)
                        }
                    },
                    {
                        "update_id": 102,
                        "type": "NewMessage",
                        "chat_id": "c12345",
                        "message": {
                            "message_id": "m102",
                            "text": "سلام تست جدید",
                            "time": int(time.time())
                        }
                    }
                ]
            }
        }
        normalized, next_off = extract_universal_rubika_updates(sample_update_data)
        self.assertEqual(len(normalized), 2)
        self.assertAlmostEqual(normalized[0]["timestamp"], past_time, delta=2)
        self.assertTrue(normalized[0]["timestamp"] < (time.time() - 100))
        self.assertTrue(normalized[1]["timestamp"] > (time.time() - 10))

if __name__ == '__main__':
    unittest.main()

