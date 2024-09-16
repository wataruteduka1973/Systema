#!/usr/bin/env python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import webbrowser
from threading import Timer


def open_browser():
    # デフォルトのWebブラウザで指定されたURLを新しいタブで開く関数
    webbrowser.open_new('http://127.0.0.1:8000/taskle/')


def main():
    """Run administrative tasks."""
    # Djangoの管理タスクを実行するための関数

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Webtaskle.settings')
    # Djangoの設定モジュールを指定する環境変数を設定
    # 'Webtaskle.settings'はプロジェクトの設定ファイルを指します

    try:
        from django.core.management import execute_from_command_line
        # Djangoのコマンドラインユーティリティをインポート
    except ImportError as exc:
        # Djangoがインポートできない場合のエラーハンドリング
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    if 'runserver' in sys.argv:
        # コマンドライン引数に'runserver'が含まれているか確認
        # 開発サーバーを起動する場合に実行されます

        port = 8000  # デフォルトポート
        for arg in sys.argv:
            if arg.startswith('0.0.0.0:') or arg.startswith('127.0.0.1:'):
                # コマンドライン引数からポート番号を取得
                port = int(arg.split(':')[1])

        if port == 8000:
            # ポートがデフォルトの8000の場合にのみブラウザを開く
            Timer(1.5, open_browser).start()
            # 1.5秒後にopen_browser関数を実行するタイマーを開始
        execute_from_command_line(sys.argv)
    # コマンドライン引数を受け取り、Djangoの管理コマンドを実行


if __name__ == '__main__':
    main()
