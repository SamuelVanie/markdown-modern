;;; demo.el --- Capture the README animation -*- lexical-binding: t; no-byte-compile: t; -*-

;; Run with scripts/record-demo.sh, in a separate graphical Emacs process.
;; Each PNG is an actual Emacs frame.  The manifest supplies playback timing,
;; so recording speed does not affect the animation's pace.

(require 'markdown-modern)

(unless (and (display-graphic-p) (fboundp 'x-export-frames))
  (error "The demo needs graphical Emacs with PNG frame export support"))

(defconst markdown-modern-demo--directory
  (file-name-as-directory (or (getenv "MARKDOWN_MODERN_DEMO_FRAMES")
                              (error "Run scripts/record-demo.sh"))))
(defvar markdown-modern-demo--frame 0)
(defvar markdown-modern-demo--manifest "ffconcat version 1.0\n")

(defun markdown-modern-demo--capture (seconds)
  "Export the current frame for SECONDS of playback."
  (message nil)
  (redisplay t)
  (let ((name (format "%04d.png" markdown-modern-demo--frame))
        (coding-system-for-write 'binary))
    (write-region (x-export-frames nil 'png) nil
                  (concat markdown-modern-demo--directory name) nil 'silent)
    (setq markdown-modern-demo--manifest
          (concat markdown-modern-demo--manifest
                  (format "file '%s'\nduration %.2f\n" name seconds))))
  (setq markdown-modern-demo--frame (1+ markdown-modern-demo--frame)))

(defun markdown-modern-demo--caption (text)
  "Show TEXT above the demo buffer."
  (setq header-line-format (concat "  markdown-modern    /    " text)))

(defun markdown-modern-demo--go (text &optional offset)
  "Set the opening position to the end of TEXT, adjusted by OFFSET."
  (goto-char (point-min))
  (search-forward text)
  (forward-char (or offset 0))
  (run-hooks 'post-command-hook))

(defun markdown-modern-demo--walk (text &optional offset)
  "Walk to the end of TEXT plus OFFSET, recording each arrow-key movement."
  (let* ((target (save-excursion
                   (goto-char (point-min))
                   (search-forward text)
                   (+ (point) (or offset 0))))
         (target-line (line-number-at-pos target))
         (steps 0))
    (while (/= (point) target)
      (when (> (setq steps (1+ steps)) 400)
        (error "Cannot walk to %S" text))
      (let* ((line (line-number-at-pos))
             (vertical (/= line target-line))
             (key (cond ((< line target-line) "<down>")
                        ((> line target-line) "<up>")
                        ((< (point) target) "<right>")
                        (t "<left>"))))
        (execute-kbd-macro (kbd key))
        (markdown-modern-demo--capture (if vertical 0.15 0.05))))))

(defun markdown-modern-demo--type (text)
  "Type TEXT through the command loop, recording each character."
  (dolist (character (string-to-list text))
    (execute-kbd-macro (vector character))
    (markdown-modern-demo--capture 0.1)))

(defun markdown-modern-demo--record ()
  "Record cursor motion, text editing, a new list item and a table edit."
  (condition-case err
      (progn
        (markdown-modern-demo--caption "Markdown, in place")
        (markdown-modern-demo--go "Read" -4)
        (markdown-modern-demo--capture 1.4)

        (markdown-modern-demo--caption "Move into text to reveal its markup")
        (markdown-modern-demo--walk "bold" -4)
        (markdown-modern-demo--capture 0.8)
        (execute-kbd-macro (kbd "M-d"))
        (markdown-modern-demo--type "styled")
        (markdown-modern-demo--capture 0.6)
        (markdown-modern-demo--caption "Keep moving: bold renders, italics reveal")
        (markdown-modern-demo--walk "emphasis" -5)
        (markdown-modern-demo--capture 0.8)
        (markdown-modern-demo--walk "*emphasis*,")
        (markdown-modern-demo--capture 0.8)

        (markdown-modern-demo--caption "Add another list item with M-RET")
        (markdown-modern-demo--walk "heading, link or code block")
        (markdown-modern-demo--capture 0.6)
        (execute-kbd-macro (kbd "M-RET"))
        (markdown-modern-demo--capture 0.5)
        (markdown-modern-demo--type "Keep adding ideas")
        (markdown-modern-demo--capture 0.8)

        (markdown-modern-demo--caption "Edit a cell; the table adjusts as you type")
        (markdown-modern-demo--walk "A clear grid" -12)
        (markdown-modern-demo--capture 1.0)
        (execute-kbd-macro (kbd "C-SPC M-f M-f M-f C-w"))
        (markdown-modern-demo--type "Columns resize as you type")
        (markdown-modern-demo--capture 1.5)
        (markdown-modern-demo--caption "Move out of the table; the grid stays aligned")
        (markdown-modern-demo--walk "Keep the source close |\n")
        (markdown-modern-demo--capture 3.0)

        ;; End on the opening state so the GIF loops without a visual jump.
        (erase-buffer)
        (insert markdown-modern-demo--source)
        (set-buffer-modified-p nil)
        (markdown-modern-demo--caption "Markdown, in place")
        (markdown-modern-demo--go "Read" -4)
        (markdown-modern-demo--capture 1.0)
        (write-region
         (concat markdown-modern-demo--manifest
                 (format "file '%04d.png'\n" (1- markdown-modern-demo--frame)))
         nil (concat markdown-modern-demo--directory "frames.ffconcat") nil 'silent)
        (kill-emacs 0))
    (error
     (princ (format "Demo recording failed: %s\n" (error-message-string err))
            'external-debugging-output)
     (kill-emacs 1))))

(load-theme 'modus-operandi t)
(menu-bar-mode -1)
(tool-bar-mode -1)
(scroll-bar-mode -1)
(blink-cursor-mode -1)
;; Integer font sizes are pixels, so desktop DPI does not change the layout.
(set-face-attribute 'default nil :font (font-spec :family "JetBrains Mono" :size 17))
(set-face-attribute 'fixed-pitch nil :font (font-spec :family "JetBrains Mono" :size 17))
(set-face-attribute 'variable-pitch nil :font (font-spec :family "Noto Sans" :size 17))
(set-face-attribute 'header-line nil :height 0.9 :box nil
                    :foreground "#454545" :background "#eeeeee")
(set-frame-size (selected-frame) 850 690 t)
(setq inhibit-startup-screen t
      inhibit-startup-message t
      initial-scratch-message nil
      ring-bell-function #'ignore
      use-dialog-box nil)
(switch-to-buffer (get-buffer-create "demo.md"))
(insert-file-contents "images/demo.md")
;; Keep the animation focused on the first three sections, without scrolling.
(goto-char (point-min))
(re-search-forward "^## Code, with colour")
(delete-region (line-beginning-position) (point-max))
(defconst markdown-modern-demo--source (buffer-string))
(markdown-modern-mode)
(setq-local mode-line-format nil
            cursor-type 'bar)
(set-buffer-modified-p nil)
(set-window-start (selected-window) (point-min))
(message nil)
;; Wait until startup has finished and the frame has its final dimensions.
(run-at-time 1 nil #'markdown-modern-demo--record)
