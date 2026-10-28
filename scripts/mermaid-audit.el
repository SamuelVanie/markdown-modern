;;; mermaid-audit.el --- Export Mermaid audit fixtures -*- lexical-binding: t; -*-

;;; Commentary:
;; Usage: emacs -Q --batch -L lisp -l scripts/mermaid-audit.el -- OUTPUT.json
;; Set MERMAID_RENDERER to an alternate .el file for a baseline comparison.

;;; Code:

(require 'json)
(require 'cl-lib)
(setq load-prefer-newer t)
(if-let* ((renderer (getenv "MERMAID_RENDERER")))
    (load renderer nil t)
  (require 'markdown-modern-mermaid))

(let* ((json-object-type 'alist)
       (json-array-type 'list)
       (cases (json-read-file "test/fixtures/mermaid-audit.json"))
       (colors '(:bg "#f8fafc" :fg "#25334a" :surface "#e8eff8"
                     :border "#8a9bb5" :accent "#2457a6")))
  (cl-letf (((symbol-function 'markdown-modern-mermaid--theme-colors)
             (lambda () colors)))
    (dolist (item cases)
      (setf (alist-get 'svg item)
            (markdown-modern-mermaid-render (alist-get 'code item)))))
  (with-temp-file (car (last command-line-args-left))
    (insert (json-encode
             `((emacs . ,emacs-version) (cases . ,(vconcat cases)))))))

;;; mermaid-audit.el ends here
