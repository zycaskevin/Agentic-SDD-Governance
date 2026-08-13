# Security Policy

## 支援範圍

目前只對最新 experimental Release 與 `main` 的安全問題進行評估。Experimental 不代表適合 Production、法規環境或未經額外 Review 的敏感資料處理。

## 回報安全問題

請優先使用 GitHub Private Vulnerability Reporting 的 **Report a vulnerability**。在該功能尚未啟用前，可先建立一個不含漏洞細節、Credential、Log 或個資的 Issue，請 Maintainer 提供私人回報管道。

請勿在公開 Issue、PR、Discussion、Screenshot 或 Chat 中提供：

- Token、Cookie、Password、OTP、Private Key。
- Production dump 或未遮罩 Log。
- 患者、付款、客戶或其他可識別個人資料。
- 可直接利用的完整 Exploit 細節。

安全回報應包含受影響版本、最小重現步驟、影響範圍與建議緩解方式，但敏感附件必須使用雙方確認的私人通道。

## Evidence 邊界

Raw Debug Evidence 必須留在 `evidence/**/private/raw/`。Local Redaction Gateway 是保守 MVP，並非法律匿名化或敏感資料安全認證。Binary evidence 在人工 Review 前不得分享。
