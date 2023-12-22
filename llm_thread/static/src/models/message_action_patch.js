/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one, attr, clear } from '@mail/model/model_field'; // Include attr
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks"; // Keep for fallback

// 1. Patch MessageActionList to add compute fields for our custom actions
registerPatch({
    name: 'MessageActionList',
    fields: {
        // Compute field for Thumb Up action
        actionThumbUp: one('MessageAction', {
            compute() {
                // Only show for assistant messages (no author)
                if (this.message && !this.message.author) {
                    return {}; // Create an instance if condition met
                }
                return clear(); // Clear otherwise
            },
            inverse: 'messageActionListOwnerAsThumbUp',
        }),
        // Compute field for Thumb Down action
        actionThumbDown: one('MessageAction', {
            compute() {
                // Only show for assistant messages (no author)
                if (this.message && !this.message.author) {
                    return {}; // Create an instance if condition met
                }
                return clear(); // Clear otherwise
            },
            inverse: 'messageActionListOwnerAsThumbDown',
        }),
    }
});


// 2. Patch MessageAction to define the behavior of our specific actions
registerPatch({
    name: 'MessageAction',
    // Add new fields (the inverse relations & computed fields)
    fields: {
        messageActionListOwnerAsThumbUp: one('MessageActionList', {
            identifying: true,
            inverse: 'actionThumbUp',
        }),
        messageActionListOwnerAsThumbDown: one('MessageActionList', {
            identifying: true,
            inverse: 'actionThumbDown',
        }),
        // Override computed properties as fields with inline compute functions
        iconClass: attr({
            compute() { // Compute function directly here
                if (this.messageActionListOwnerAsThumbUp) {
                    const message = this.messageActionListOwnerAsThumbUp.message;
                    const isVoted = message && message.user_vote === 1;
                    return `fa fa-thumbs-up ${isVoted ? 'text-primary fw-bold' : ''}`;
                }
                if (this.messageActionListOwnerAsThumbDown) {
                    const message = this.messageActionListOwnerAsThumbDown.message;
                    const isVoted = message && message.user_vote === -1;
                    return `fa fa-thumbs-down ${isVoted ? 'text-primary fw-bold' : ''}`;
                }
                // Call super compute if it exists (this structure is complex for attr)
                // Note: Correctly calling super for attr compute is tricky.
                // Often, core Odoo doesn't override computed attrs this way,
                // but rather uses more complex relations or states.
                // Assuming direct super call isn't standard for attr compute.
                // If needed, a more complex patch involving inheritance might be required.
                // For now, let's assume base iconClass is empty if not our actions.
                 const originalCompute = this._super && this._super.constructor.props.fields.iconClass && this._super.constructor.props.fields.iconClass.compute;
                 return originalCompute ? originalCompute.call(this) : '';
            },
        }),
        label: attr({
            compute() { // Compute function directly here
                if (this.messageActionListOwnerAsThumbUp) {
                    return _t("Thumb Up");
                }
                if (this.messageActionListOwnerAsThumbDown) {
                    return _t("Thumb Down");
                }
                 const originalCompute = this._super && this._super.constructor.props.fields.label && this._super.constructor.props.fields.label.compute;
                 return originalCompute ? originalCompute.call(this) : '';
            },
        }),
        sequence: attr({
            compute() { // Compute function directly here
                 // Position thumbs actions: e.g., Star (10), Thumbs (15, 16), Reply (20)
                if (this.messageActionListOwnerAsThumbUp) {
                    return 15;
                }
                if (this.messageActionListOwnerAsThumbDown) {
                    return 16;
                }
                 const originalCompute = this._super && this._super.constructor.props.fields.sequence && this._super.constructor.props.fields.sequence.compute;
                 return originalCompute ? originalCompute.call(this) : 100; // Default high sequence
            },
        }),
        isVisible: attr({ // Added for consistency
             compute() { // Compute function directly here
                 if (this.messageActionListOwnerAsThumbUp || this.messageActionListOwnerAsThumbDown) {
                     return true; // Visibility is handled by compute() in MessageActionList
                 }
                  const originalCompute = this._super && this._super.constructor.props.fields.isVisible && this._super.constructor.props.fields.isVisible.compute;
                 return originalCompute ? originalCompute.call(this) : true; // Default true
             },
        }),
    },
    // Add/Override record methods
    recordMethods: {
        // Override execute to handle voting logic (remains the same)
        async _execute(ev) {
            let rpc;
            // Standard way to get RPC service in models
            if (this.messaging && this.messaging.rpc) {
                rpc = this.messaging.rpc;
            } else {
                console.warn("RPC service not found via this.messaging.rpc in MessageAction patch.");
            }

            if (!rpc) {
                console.error("RPC service not available for MessageAction execute.");
                return this._super ? this._super(...arguments) : undefined;
            }

            let message, currentVote, newVote, voteValue;

            if (this.messageActionListOwnerAsThumbUp) {
                message = this.messageActionListOwnerAsThumbUp.message;
                if (!message) return;
                currentVote = message.user_vote;
                newVote = currentVote === 1 ? 0 : 1;
                voteValue = 1;
            } else if (this.messageActionListOwnerAsThumbDown) {
                message = this.messageActionListOwnerAsThumbDown.message;
                if (!message) return;
                currentVote = message.user_vote;
                newVote = currentVote === -1 ? 0 : -1;
                voteValue = -1;
            } else {
                return this._super ? this._super(...arguments) : undefined;
            }

            try {
                await rpc("/llm/message/vote", {
                    message_id: message.id,
                    vote_value: newVote,
                });
                message.update({ user_vote: newVote });
            } catch (error) {
                console.error(`Error voting ${voteValue === 1 ? 'up' : 'down'}:`, error);
                if (this.env && this.env.services.notification) {
                    this.env.services.notification.add(_t("Failed to record vote."), { type: 'danger' });
                } else {
                     console.warn("Notification service not available to display vote failure.");
                }
            }
        },
    },
    // NO computeMethods block needed here
});
