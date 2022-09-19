/** @odoo-module **/

import { useRefToModel } from '@mail/component_hooks/use_ref_to_model';
import { useUpdate } from '@mail/component_hooks/use_update';
import { registerMessagingComponent } from '@mail/utils/messaging_component';

const { Component } = owl;

export class LLMChatComposerTextInput extends Component {
    /**
     * @override
     */
    setup() {
        super.setup();
        useRefToModel({ fieldName: 'mirroredTextareaRef', refName: 'mirroredTextarea' });
        useRefToModel({ fieldName: 'textareaRef', refName: 'textarea' });
        useUpdate({ func: () => this._update() });
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {ComposerView}
     */
    get composerView() {
        return this.props.record;
    }

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _isEmpty() {
        return this.composerView.textareaRef.el.value === "";
    }

    /**
     * Intercept input event before passing to composer view
     * @private
     * @param {InputEvent} ev
     */
    _onInput(ev) {
        // Pre-process the input if needed
        const value = ev.target.value;
        
        // Call original handler
        this.composerView.onInputTextarea(ev);
        
        // Update textarea height
        this._updateTextInputHeight();
    }

    /**
     * Intercept keydown event
     * @private
     * @param {KeyboardEvent} ev
     */
    _onKeydown(ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            // Pre-process before sending if needed
            this.composerView.onClickSend();
            return;
        }
        
        this.composerView.onKeydownTextarea(ev);
    }

    /**
     * @private
     */
    _update() {
        if (!this.root.el) {
            return;
        }

        if (this.composerView.doFocus) {
            this.composerView.update({ doFocus: false });
            this.composerView.textareaRef.el.focus();
        }

        if (this.composerView.hasToRestoreContent) {
            this.composerView.textareaRef.el.value = this.composerView.composer.textInputContent;
            
            if (this.composerView.isFocused) {
                this.composerView.textareaRef.el.setSelectionRange(
                    this.composerView.composer.textInputCursorStart,
                    this.composerView.composer.textInputCursorEnd,
                    this.composerView.composer.textInputSelectionDirection,
                );
            }
            
            this.composerView.update({ hasToRestoreContent: false });
        }

        this._updateTextInputHeight();
    }

    /**
     * @private
     */
    _updateTextInputHeight() {
        const mirroredTextarea = this.composerView.mirroredTextareaRef.el;
        const textarea = this.composerView.textareaRef.el;
        
        mirroredTextarea.value = textarea.value;
        textarea.style.height = mirroredTextarea.scrollHeight + 'px';
    }
}

Object.assign(LLMChatComposerTextInput, {
    props: { record: Object },
    template: 'llm_thread.LLMChatComposerTextInput',
});

registerMessagingComponent(LLMChatComposerTextInput);