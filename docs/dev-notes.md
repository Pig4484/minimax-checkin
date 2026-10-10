# 開發筆記（dev-notes）

本專案以 **Cline + AI 模型協作**開發：

- [Muse Spark](https://www.muse.com/) `muse-spark`
 （`cline/free-muse-spark-1.3`，contributor 免費額度）負責主要實作與除錯。
- [DeepSeek](https://www.deepseek.com/) `deepseek-v4.1-flash` 負責初版雛形。

## 開發心得

DeepSeek v4.1 相比上一代進步巨大，多模態讓它在看 UI 截圖時表現好很多，
但不少地方是用輸出長度堆智力，容易一次造出一堆 bug；後來換 Muse Spark 把 bug 逐一修掉，
才有現在這個穩定可用的版本。

## 介面參考

- 介面風格與技術棧參考開源專案
  [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0），
  技術同為 **PySide6 + PySide6-Fluent-Widgets**（Microsoft Fluent Design）。
