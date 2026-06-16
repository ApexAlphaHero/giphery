package com.giphery.app

import app.cash.turbine.test
import com.giphery.app.data.repo.AuthRepository
import com.giphery.app.ui.pairing.PairingViewModel
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class PairingViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private val authRepository: AuthRepository = mockk()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `canSubmit requires https url code and username`() {
        val vm = PairingViewModel(authRepository)
        assertFalse(vm.state.value.canSubmit)

        vm.onBaseUrl("https://giphery.example.com")
        vm.onCode("ABCDE-FGHIJ-KLMNO-PQRST-UVWXY")
        vm.onUsername("alice")

        assertTrue(vm.state.value.canSubmit)
    }

    @Test
    fun `code is auto-hyphenated uppercased and capped`() {
        val vm = PairingViewModel(authRepository)
        vm.onCode("abcde fghij12345")
        assertEquals("ABCDE-FGHIJ-12345", vm.state.value.code)

        // Pasting the already-hyphenated form is idempotent.
        vm.onCode("ABCDE-FGHIJ-12345")
        assertEquals("ABCDE-FGHIJ-12345", vm.state.value.code)
    }

    @Test
    fun `successful pair sets paired true`() = runTest(dispatcher) {
        coEvery { authRepository.pair(any(), any(), any()) } returns Result.success(Unit)
        val vm = PairingViewModel(authRepository)
        vm.onBaseUrl("https://giphery.example.com")
        vm.onCode("ABCDE-FGHIJ-KLMNO-PQRST-UVWXY")
        vm.onUsername("alice")

        vm.state.test {
            assertEquals(false, awaitItem().paired) // initial
            vm.submit()
            // loading=true emission
            awaitItem()
            // paired=true emission
            assertTrue(awaitItem().paired)
            cancelAndIgnoreRemainingEvents()
        }
    }
}
