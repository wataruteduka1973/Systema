@echo off
REM 仮想環境がなければ作成
if not exist venv (
    python -m venv venv
)

REM 仮想環境を有効化
call venv\Scripts\activate

REM 必要なパッケージをインストール
pip install --upgrade pip
pip install -r requirements.txt

REM マイグレーションが必要かチェックし、必要なら実行
python manage.py showmigrations --plan | findstr "\[ \]" > nul
if %errorlevel%==0 (
    echo Perform migration...
    python manage.py migrate
) else (
    echo No migration needed.
)

REM サーバー起動
python manage.py runserver

REM 終了時に仮想環境を無効化
deactivate
pause