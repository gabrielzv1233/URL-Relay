$ErrorActionPreference = "Stop"

python -m nuitka `
    --mode=standalone `
    --assume-yes-for-downloads `
    --include-data-file=config.json=config.json `
    --include-data-file=url_receiver.ico=url_receiver.ico `
    --windows-console-mode=disable `
    --windows-icon-from-ico=url_receiver.ico `
    --windows-company-name="Gabrielzv1233" `
    --windows-product-name="URL Channel Receiver" `
    --windows-file-description="Receives URLs from a configured WebSocket channel." `
    --windows-file-version="1.0.0.0" `
    --windows-product-version="1.0.0.0" `
    --output-filename="URLChannelReceiver.exe" `
    receiver.py
