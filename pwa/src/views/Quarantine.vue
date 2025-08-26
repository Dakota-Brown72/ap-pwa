<template>
  <div class="min-h-screen bg-base-200 flex items-center justify-center p-6">
    <div class="card max-w-md w-full bg-base-100 shadow-lg">
      <div class="card-body text-base-content text-center">
        <h2 class="card-title justify-center">Access Temporarily Restricted</h2>
        <p class="mt-2">Your account is currently disabled and cannot access AnchorPoint at this time.</p>
        <p class="text-sm text-base-content/70">If you believe this is an error, please contact your system administrator.</p>
        <div class="mt-4">
          <router-link to="/login" class="btn btn-primary btn-sm">Back to Login</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default { name: 'Quarantine' }
</script> 