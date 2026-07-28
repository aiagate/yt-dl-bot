import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import SecretStr



from yt_dl_bot import discord_bot_main


class LoggingConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.log_path = Path(self.temporary_directory.name) / 'nested/logs'
        self.target_loggers = [
            logging.getLogger(name)
            for name in discord_bot_main.FILE_LOGGERS
        ]

    def tearDown(self):
        seen = set()
        for logger in self.target_loggers:
            for handler in tuple(logger.handlers):
                if (
                    isinstance(handler, logging.FileHandler)
                    and Path(handler.baseFilename).parent == self.log_path
                ):
                    logger.removeHandler(handler)
                    if id(handler) not in seen:
                        handler.close()
                        seen.add(id(handler))

    def test_configures_level_formatter_and_target_loggers(self):
        handler = discord_bot_main.configure_logging(self.log_path)

        self.assertTrue(self.log_path.is_dir())
        self.assertEqual(handler.level, logging.INFO)
        self.assertEqual(
            handler.formatter._fmt,
            discord_bot_main.LOG_FORMAT,
        )
        self.assertEqual(
            handler.formatter.datefmt,
            discord_bot_main.LOG_DATE_FORMAT,
        )
        for logger in self.target_loggers:
            with self.subTest(logger=logger.name):
                self.assertEqual(logger.level, logging.INFO)
                self.assertIn(handler, logger.handlers)

    def test_repeated_configuration_does_not_duplicate_handlers(self):
        first = discord_bot_main.configure_logging(self.log_path)
        second = discord_bot_main.configure_logging(self.log_path)

        self.assertIs(first, second)
        for logger in self.target_loggers:
            matching = [
                handler
                for handler in logger.handlers
                if (
                    isinstance(handler, logging.FileHandler)
                    and Path(handler.baseFilename).parent == self.log_path
                )
            ]
            self.assertEqual(len(matching), 1)

    def test_main_configures_logging_before_bot_run(self):
        events = []
        settings = SimpleNamespace(
            LOG_PATH=self.log_path,
            DISCORD_KEY=SecretStr('super-secret-token'),
        )
        services = Mock(name='services')
        bot = Mock()
        bot.run.side_effect = lambda token: events.append(('run', token))

        with (
            patch.object(
                discord_bot_main,
                'configure_logging',
                side_effect=lambda path: events.append(('logging', path)),
            ),
            patch.object(
                discord_bot_main.ApplicationServices,
                'from_settings',
                return_value=services,
            ),
            patch.object(
                discord_bot_main,
                'MyBot',
                return_value=bot,
            ) as bot_class,
        ):
            discord_bot_main.main(settings)

        self.assertEqual(
            events,
            [
                ('logging', self.log_path),
                ('run', 'super-secret-token'),
            ],
        )
        bot_class.assert_called_once_with(
            command_prefix='!',
            settings=settings,
            services=services,
        )

    def test_logging_configuration_does_not_write_secret_values(self):
        discord_bot_main.configure_logging(self.log_path)

        contents = (self.log_path / 'discord_bot_main.log').read_text()

        self.assertNotIn('super-secret-token', contents)


if __name__ == '__main__':
    unittest.main()
