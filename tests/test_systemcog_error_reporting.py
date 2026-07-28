import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


SOURCE_PATH = Path(__file__).resolve().parents[1] / 'source'
sys.path.insert(0, str(SOURCE_PATH))

from cogs.systemcog import SystemCog
from error_reporting import format_exception_traceback


class SendErrorLogTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.channel = Mock(mention='#logs')
        self.channel.send = AsyncMock()
        self.bot = Mock(
            settings=SimpleNamespace(LOG_CHANNEL=1),
            logger=Mock(),
        )
        self.bot.get_channel.return_value = self.channel
        self.cog = SystemCog(self.bot)
        self.ctx = Mock(reply=AsyncMock())

    @staticmethod
    def _long_exception():
        try:
            raise RuntimeError('x' * 30_000)
        except RuntimeError as error:
            return error

    async def test_long_traceback_is_sent_as_valid_embeds_and_logged_in_full(self):
        error = self._long_exception()
        expected_log = format_exception_traceback(error)

        await SystemCog.send_error_log.callback(self.cog, self.ctx, error)

        self.bot.logger.error.assert_called_once_with(expected_log)
        self.assertGreater(self.channel.send.await_count, 1)
        sent_values = []
        for sent_call in self.channel.send.await_args_list:
            embed = sent_call.kwargs['embed']
            self.assertLessEqual(len(embed.fields), 5)
            self.assertLessEqual(len(embed), 6000)
            for field in embed.fields:
                self.assertLessEqual(len(field.value), 1024)
                sent_values.append(field.value)
        self.assertEqual(''.join(sent_values), expected_log)

    async def test_complete_traceback_is_logged_before_notification_failure(self):
        error = self._long_exception()
        expected_log = format_exception_traceback(error)
        self.ctx.reply.side_effect = RuntimeError('Discord unavailable')

        with self.assertRaisesRegex(RuntimeError, 'Discord unavailable'):
            await SystemCog.send_error_log.callback(self.cog, self.ctx, error)

        self.bot.logger.error.assert_called_once_with(expected_log)
        self.channel.send.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
