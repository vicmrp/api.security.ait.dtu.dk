// Auto-pick an action based on filled action form fields
(function() {
  function onSubmit(e) {
    try {
      var form = document.getElementById('changelist-form');
      if (!form) return;
      var actionSelect = form.querySelector('select[name="action"]');
      if (!actionSelect) return;

      if (actionSelect.value) return; // user already picked an action

      // If limiter_type is selected, choose bulk_set_limiter_type
      var limiter = form.querySelector('select[name="limiter_type"]');
      if (limiter && limiter.value) {
        actionSelect.value = 'bulk_set_limiter_type';
        return;
      }

      // If any ad_groups chosen, choose bulk_add_ad_groups
      var adGroups = form.querySelector('select[name="ad_groups"]');
      if (adGroups) {
        for (var i = 0; i < adGroups.options.length; i++) {
          if (adGroups.options[i].selected) {
            actionSelect.value = 'bulk_add_ad_groups';
            return;
          }
        }
      }
    } catch (err) {
      // no-op; fall through to default admin behavior
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    var form = document.getElementById('changelist-form');
    if (form) {
      form.addEventListener('submit', onSubmit, true);
    }
  });
})();

