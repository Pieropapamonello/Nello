import unittest
from link_keys import link_key


class YouTubeKeys(unittest.TestCase):
    def test_watch_videos_have_distinct_case_sensitive_identities(self):
        self.assertNotEqual(link_key('https://youtube.com/watch?v=vBNE3bKMpu8'),
                            link_key('https://youtube.com/watch?v=a8D8awQaneo'))
        self.assertNotEqual(link_key('https://youtube.com/watch?v=a8D8awQaneo'),
                            link_key('https://youtube.com/watch?v=a8d8awqaneo'))

    def test_all_url_forms_share_one_key_and_skip_tracking(self):
        ident = 'z9A1Wf695sQ'
        for url in ('https://youtu.be/' + ident + '?si=tracking',
                    'https://youtube.com/shorts/' + ident,
                    'https://youtube.com/watch?v=' + ident + '&t=12',
                    'https://m.youtube.com/embed/' + ident):
            self.assertEqual(link_key(url), 'youtube.com/video/' + ident)

    def test_existing_broken_cache_namespace_is_not_reused(self):
        self.assertNotEqual(link_key('https://youtube.com/watch?v=a8D8awQaneo'), 'youtube.com/watch')


class FacebookPostCacheTests(unittest.TestCase):
    def test_old_share_cache_is_invalidated_and_token_case_preserved(self):
        key = link_key('https://www.facebook.com/share/14suwq5RADU/?mibextid=tracking')
        self.assertEqual(key, 'facebook-post-v2/share/14suwq5RADU')
        self.assertNotEqual(key, link_key('https://www.facebook.com/share/14suwq5radu/'))


class LinkKeyTests(unittest.TestCase):
    def test_photo_ids_never_share_cache(self):
        self.assertNotEqual(link_key('https://www.facebook.com/photo/?fbid=123'),
                            link_key('https://www.facebook.com/photo/?fbid=456'))
        self.assertNotEqual(link_key('https://www.facebook.com/photo/?fbid=123'), 'facebook.com/photo')

    def test_photo_variants_share_identity(self):
        self.assertEqual(link_key('https://www.facebook.com/photo/?fbid=123&set=a.45'),
                         link_key('https://m.facebook.com/photo.php?set=a.45&fbid=123'))

    def test_other_links_remain_compatible(self):
        self.assertEqual(link_key('https://www.instagram.com/reel/ABC/?tracking=1'), 'instagram.com/reel/abc')
        self.assertEqual(link_key('https://www.facebook.com/reel/123/'), 'facebook.com/reel/123')
